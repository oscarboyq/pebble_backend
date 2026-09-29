from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase

from cart.models import Cart, CartItem
from coupons.models import Coupon
from home.models import ProductsBundleSection
from orders.models import Order
from products.models import Category, Product, ProductVariant


ADDRESS = {
    'full_name': 'Demo Buyer', 'phone': '5551234567',
    'address_line1': '1 Test Lane', 'city': 'Dhaka',
    'state': 'Dhaka', 'postal_code': '1200', 'country': 'Bangladesh',
}


class PricingCheckoutTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('buyer', password='test')
        self.client.force_authenticate(self.user)
        category = Category.objects.create(name='Tops', slug='tops')
        self.first = Product.objects.create(category=category, name='Top', slug='top', price='10.00')
        self.second = Product.objects.create(category=category, name='Tank', slug='tank', price='20.00')
        self.first_variant = ProductVariant.objects.create(product=self.first, size='S', stock=10)
        self.second_variant = ProductVariant.objects.create(product=self.second, size='S', stock=10)
        self.cart = Cart.objects.create(user=self.user)

    def add(self, product, variant, quantity=1):
        return self.client.post('/api/cart/items/', {
            'product_slug': product.slug, 'variant_id': variant.id, 'quantity': quantity,
        }, format='json')

    def bundle(self):
        bundle = ProductsBundleSection.objects.create(
            heading='Pair & Save 10%', discount_percentage=10,
            banner_image='bundle_banners/test.jpg',
        )
        bundle.bundle_products.set([self.first, self.second])
        return bundle

    def test_bundle_add_is_atomic_and_uses_configured_products(self):
        bundle = self.bundle()
        payload = {'bundle_id': bundle.id, 'variant_ids': [self.first_variant.id, self.second_variant.id]}
        response = self.client.post('/api/cart/bundles/', payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['item_count'], 2)
        self.assertEqual((response.data['subtotal'], response.data['discount'], response.data['total']), (30.0, 3.0, 27.0))
        self.second_variant.stock = 0
        self.second_variant.save(update_fields=['stock'])
        rejected = self.client.post('/api/cart/bundles/', payload, format='json')
        self.assertEqual(rejected.status_code, 400)
        self.assertIn('Only 0 units', rejected.data['detail'])
        self.assertEqual(list(self.cart.items.order_by('variant_id').values_list('quantity', flat=True)), [1, 1])
        invalid = self.client.post('/api/cart/bundles/', {
            'bundle_id': bundle.id, 'variant_ids': [self.first_variant.id, self.first_variant.id],
        }, format='json')
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(self.cart.items.count(), 2)

    def coupon(self, code='SAVE20', **kwargs):
        return Coupon.objects.create(
            code=code, discount_type=kwargs.pop('discount_type', 'percent'),
            discount_value=kwargs.pop('discount_value', Decimal('20.00')),
            **kwargs,
        )

    def test_normal_cart_and_checkout_snapshot(self):
        self.assertEqual(self.add(self.first, self.first_variant, 2).status_code, 200)
        quote = self.client.get('/api/cart/').data
        self.assertEqual((quote['subtotal'], quote['discount'], quote['total']), (20.0, 0.0, 20.0))
        response = self.client.post('/api/orders/place/', ADDRESS, format='json')
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.data['id'])
        self.assertEqual([event['status'] for event in response.data['status_events']], ['pending'])
        self.assertEqual((order.subtotal_amount, order.discount_amount, order.total_amount),
                         (Decimal('20.00'), Decimal('0.00'), Decimal('20.00')))
        self.assertEqual(order.pricing_snapshot['total'], '20.00')
        self.first_variant.refresh_from_db()
        self.assertEqual(self.first_variant.stock, 8)
        self.assertEqual(self.cart.items.count(), 0)

    def test_bundle_discount_counts_only_complete_pairs(self):
        self.bundle()
        self.add(self.first, self.first_variant, 3)
        self.add(self.second, self.second_variant, 2)
        quote = self.client.get('/api/cart/').data
        self.assertEqual((quote['subtotal'], quote['discount'], quote['total']), (70.0, 6.0, 64.0))
        self.assertEqual(quote['applied_offer']['pairs'], 2)

    def test_coupon_only_and_better_offer_wins_without_stacking(self):
        self.bundle()
        self.add(self.first, self.first_variant)
        self.add(self.second, self.second_variant)
        coupon = self.coupon()
        response = self.client.post('/api/cart/coupon/', {'code': 'save20'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.data['discount'], response.data['total']), (6.0, 24.0))
        self.assertEqual(response.data['applied_offer']['type'], 'coupon')
        order_response = self.client.post('/api/orders/place/', ADDRESS, format='json')
        self.assertEqual(order_response.status_code, 201)
        coupon.refresh_from_db()
        self.assertEqual(coupon.usage_count, 1)
        self.assertEqual(Order.objects.get().total_amount, Decimal('24.00'))

        # A smaller coupon remains eligible but the bundle wins; it is not consumed.
        self.add(self.first, self.first_variant)
        self.add(self.second, self.second_variant)
        small = self.coupon('SMALL', discount_value=Decimal('5.00'))
        response = self.client.post('/api/cart/coupon/', {'code': 'SMALL'}, format='json')
        self.assertEqual(response.data['applied_offer']['type'], 'bundle')
        self.assertEqual(response.data['discount'], 3.0)
        self.assertEqual(self.client.post('/api/orders/place/', ADDRESS, format='json').status_code, 201)
        small.refresh_from_db()
        self.assertEqual(small.usage_count, 0)

    def test_fixed_coupon_caps_at_subtotal_and_invalid_codes_fail(self):
        self.add(self.first, self.first_variant)
        self.assertEqual(self.client.post('/api/cart/coupon/', {'code': 'MISSING'}, format='json').status_code, 400)
        coupon = self.coupon('BIG', discount_type='fixed', discount_value=Decimal('50.00'))
        response = self.client.post('/api/cart/coupon/', {'code': 'BIG'}, format='json')
        self.assertEqual((response.data['discount'], response.data['total']), (10.0, 0.0))
        self.assertEqual(self.client.delete('/api/cart/coupon/').data['total'], 10.0)

    def test_expiry_minimum_and_usage_limit_are_enforced_at_checkout(self):
        self.add(self.first, self.first_variant)
        expired = self.coupon('OLD', expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.client.post('/api/cart/coupon/', {'code': expired.code}, format='json').status_code, 400)
        minimum = self.coupon('MIN', min_order_amount=Decimal('25.00'))
        self.assertEqual(self.client.post('/api/cart/coupon/', {'code': minimum.code}, format='json').status_code, 400)
        limited = self.coupon('ONE', usage_limit=1)
        self.assertEqual(self.client.post('/api/cart/coupon/', {'code': limited.code}, format='json').status_code, 200)
        limited.usage_count = 1
        limited.save(update_fields=['usage_count'])
        response = self.client.post('/api/orders/place/', ADDRESS, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('usage limit', response.data['detail'])
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(self.cart.items.count(), 1)

    def test_unavailable_stock_and_legacy_variantless_items_cannot_order(self):
        self.assertEqual(self.add(self.first, self.first_variant, 11).status_code, 400)
        self.add(self.first, self.first_variant, 2)
        self.first_variant.stock = 1
        self.first_variant.save(update_fields=['stock'])
        response = self.client.post('/api/orders/place/', ADDRESS, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Only 1', response.data['detail'])
        self.assertEqual(Order.objects.count(), 0)
        self.first_variant.refresh_from_db()
        self.assertEqual(self.first_variant.stock, 1)
        self.cart.items.all().delete()
        CartItem.objects.create(cart=self.cart, product=self.first, quantity=1)
        response = self.client.post('/api/orders/place/', ADDRESS, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Select an available variant', response.data['detail'])
