from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from home.models import LookbookCard, LookbookHotspot, MarqueeItem, NewsletterSubscriber
from products.models import Category, Product, ProductLink


class CatalogContentApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user('owner', password='test', is_staff=True)
        category = Category.objects.create(name='T-Shirts', slug='t-shirts')
        self.source = Product.objects.create(category=category, name='Basic Tee', slug='basic-tee', price='20.00')
        self.first = Product.objects.create(category=category, name='Blue Tee', slug='blue-tee', price='21.00')
        self.second = Product.objects.create(category=category, name='Red Tee', slug='red-tee', price='22.00')

    def test_owner_curates_ordered_directed_links_and_public_outfit(self):
        url = f'/api/admin/products/{self.source.id}/links/outfit/'
        self.assertEqual(self.client.put(url, {'product_ids': [self.second.id]}, format='json').status_code, 401)
        self.client.force_authenticate(self.admin)
        response = self.client.put(url, {'product_ids': [self.second.id, self.first.id]}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['product_ids'], [self.second.id, self.first.id])
        self.assertEqual(list(ProductLink.objects.filter(source=self.source).values_list('target_id', flat=True)), [self.second.id, self.first.id])
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/products/basic-tee/related/?intent=outfit')
        self.assertEqual([p['id'] for p in response.data['products']], [self.second.id, self.first.id])
        self.assertEqual(self.client.get('/api/products/red-tee/related/?intent=outfit').data['products'], [])

    def test_link_input_rejects_duplicates_self_and_missing_products_without_mutation(self):
        self.client.force_authenticate(self.admin)
        url = f'/api/admin/products/{self.source.id}/links/related/'
        for ids in ([self.first.id, self.first.id], [self.source.id], [999999]):
            self.assertEqual(self.client.put(url, {'product_ids': ids}, format='json').status_code, 400)
        self.assertEqual(ProductLink.objects.count(), 0)

    def test_hotspot_coordinates_and_legacy_tags_stay_in_sync(self):
        card = LookbookCard.objects.create(title='Playful Look', image='lookbook_cards/test.jpg')
        self.client.force_authenticate(self.admin)
        url = f'/api/admin/home/lookbooks/{card.id}/hotspots/'
        invalid = {'hotspots': [{'product_id': self.first.id, 'desktop_x': 120, 'desktop_y': 20}]}
        self.assertEqual(self.client.put(url, invalid, format='json').status_code, 400)
        payload = {'hotspots': [{'product_id': self.first.id, 'desktop_x': 40, 'desktop_y': 20, 'mobile_x': 55, 'mobile_y': 30}]}
        self.assertEqual(self.client.put(url, payload, format='json').status_code, 200)
        self.assertEqual(card.tagged_products.count(), 1)
        self.assertEqual(LookbookHotspot.objects.get(card=card).mobile_x, 55)

    def test_legacy_lookbook_edits_sync_unpositioned_hotspots(self):
        card = LookbookCard.objects.create(title='Weekend Look', image='lookbook_cards/test.jpg')
        card.tagged_products.add(self.first)
        self.assertTrue(LookbookHotspot.objects.filter(card=card, product=self.first, desktop_x__isnull=True).exists())
        card.tagged_products.remove(self.first)
        self.assertFalse(LookbookHotspot.objects.filter(card=card, product=self.first).exists())

    def test_owner_content_validation_and_public_newsletter(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/admin/home/content/marquee-items/', {'text': 'Soft cotton', 'order': 7}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(MarqueeItem.objects.filter(text='Soft cotton').exists())
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.post('/api/home/newsletter/', {'email': 'wrong'}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/home/newsletter/', {'email': 'Parent@Example.com'}, format='json').status_code, 201)
        self.assertEqual(self.client.post('/api/home/newsletter/', {'email': 'parent@example.com'}, format='json').status_code, 200)
        self.assertEqual(NewsletterSubscriber.objects.count(), 1)

    def test_typed_editorial_destination_updates_route(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/admin/home/content/pages-menu-links/', {
            'label': 'Basic Tee',
            'destination_product': self.source.id, 'order': 3,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['route'], '/products/basic-tee')
        bad = self.client.patch(f"/api/admin/home/content/pages-menu-links/{response.data['id']}/", {
            'destination_collection': 999999,
        }, format='json')
        self.assertEqual(bad.status_code, 400)
