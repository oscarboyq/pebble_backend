from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from products.models import Category, Product, ProductVariant
from .models import Order, OrderItem, OrderStatusEvent


class OrderTrackingTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user('buyer', password='test')
        self.other = User.objects.create_user('other', password='test')
        self.owner = User.objects.create_user('owner', password='test', is_staff=True)
        category = Category.objects.create(name='T-Shirts', slug='t-shirts')
        product = Product.objects.create(category=category, name='Basic Tee', slug='basic-tee', price='20.00')
        self.variant = ProductVariant.objects.create(product=product, color='Blue', size='4', stock=7)
        self.order = Order.objects.create(
            user=self.customer, full_name='Buyer', phone='123', address_line1='1 Main St',
            city='City', state='State', postal_code='12345', total_amount='40.00',
        )
        OrderItem.objects.create(
            order=self.order, product=product, variant=self.variant,
            quantity=2, unit_price='20.00', line_total='40.00',
        )
        OrderStatusEvent.objects.create(
            order=self.order, status='pending', occurred_at=self.order.created_at,
        )

    def test_only_owner_can_change_status_and_only_buyer_can_read(self):
        url = f'/api/orders/{self.order.id}/'
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get(url).data['status_events'][0]['status'], 'pending')
        self.assertEqual(self.client.patch(f'/api/admin/orders/{self.order.id}/', {'status': 'confirmed'}).status_code, 403)

    def test_owner_milestones_and_shipping_edits_reach_buyer(self):
        self.client.force_authenticate(self.owner)
        url = f'/api/admin/orders/{self.order.id}/'
        self.assertEqual(self.client.patch(url, {'status': 'shipped'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(url, {'status': 'confirmed'}, format='json').status_code, 200)
        shipped = self.client.patch(url, {
            'status': 'shipped', 'carrier': 'dhl', 'tracking_number': 'DHL123',
            'tracking_url': 'https://www.dhl.com/global-en/home/tracking.html?tracking-id=DHL123',
            'estimated_delivery': '2026-10-10', 'shipping_notes': 'Packed safely',
        }, format='json')
        self.assertEqual(shipped.status_code, 200)
        shipped_at = shipped.data['shipped_at']
        self.assertEqual([event['status'] for event in shipped.data['status_events']],
                         ['pending', 'confirmed', 'shipped'])
        edited = self.client.patch(url, {
            'status': 'shipped', 'tracking_number': 'DHL456',
        }, format='json')
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.data['shipped_at'], shipped_at)
        self.assertEqual(len(edited.data['status_events']), 3)
        self.assertEqual(self.client.patch(url, {'status': 'delivered'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(url, {'status': 'pending'}, format='json').status_code, 400)
        self.client.force_authenticate(self.customer)
        visible = self.client.get(f'/api/orders/{self.order.id}/').data
        self.assertEqual(visible['tracking_number'], 'DHL456')
        self.assertTrue(visible['tracking_url'].startswith('https://www.dhl.com/'))
        self.assertEqual([event['status'] for event in visible['status_events']],
                         ['pending', 'confirmed', 'shipped', 'delivered'])

    def test_cancel_restocks_once_and_rejects_repeat(self):
        self.client.force_authenticate(self.owner)
        url = f'/api/admin/orders/{self.order.id}/'
        self.assertEqual(self.client.patch(url, {'status': 'cancelled'}, format='json').status_code, 200)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 9)
        self.assertEqual(self.client.patch(url, {'status': 'cancelled'}, format='json').status_code, 400)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 9)
        self.assertEqual(OrderStatusEvent.objects.filter(order=self.order, status='cancelled').count(), 1)

    def test_invalid_shipping_details_do_not_change_order(self):
        self.client.force_authenticate(self.owner)
        url = f'/api/admin/orders/{self.order.id}/'
        self.client.patch(url, {'status': 'confirmed'}, format='json')
        self.assertEqual(self.client.patch(url, {
            'status': 'shipped', 'carrier': 'invalid',
        }, format='json').status_code, 400)
        self.assertEqual(self.client.patch(url, {
            'status': 'shipped', 'tracking_url': 'http://example.com/track',
        }, format='json').status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'confirmed')
