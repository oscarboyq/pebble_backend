from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APITestCase

from merchandising.models import SmartCollection
from products.models import Category, Product


class HotThisWeekApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user('owner', password='test', is_staff=True)
        category = Category.objects.create(name='T-Shirts', slug='t-shirts')
        self.products = [
            Product.objects.create(category=category, name=name, slug=slug, price='20.00')
            for name, slug in [
                ('Logo Polo Red', 'logo-polo-red'),
                ('Basic Tee', 'basic-tee'),
                ('Stripe Backpack Brown', 'stripe-backpack-brown'),
            ]
        ]
        self.best = SmartCollection.objects.get(slug='best-sellers')
        self.new = SmartCollection.objects.get(slug='new-arrivals')

    def test_owner_pins_keep_home_tabs_distinct_and_refresh_public_data(self):
        self.client.force_authenticate(self.owner)
        for collection, ids in [
            (self.best, [self.products[0].id, self.products[2].id]),
            (self.new, [self.products[1].id, self.products[2].id]),
        ]:
            response = self.client.put(
                f'/api/admin/collections/{collection.id}/products/',
                {'pinned_product_ids': ids}, format='json',
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['pinned_product_ids'], ids)

        self.client.force_authenticate(user=None)
        response = self.client.get('/api/home/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [product['slug'] for product in response.data['best_sellers'][:2]],
            ['logo-polo-red', 'stripe-backpack-brown'],
        )
        self.assertEqual(
            [product['slug'] for product in response.data['new_arrivals'][:2]],
            ['basic-tee', 'stripe-backpack-brown'],
        )

        self.client.force_authenticate(self.owner)
        self.client.put(
            f'/api/admin/collections/{self.new.id}/products/',
            {'pinned_product_ids': [self.products[2].id, self.products[1].id]},
            format='json',
        )
        self.client.force_authenticate(user=None)
        refreshed = self.client.get('/api/home/')
        self.assertEqual(
            [product['slug'] for product in refreshed.data['new_arrivals'][:2]],
            ['stripe-backpack-brown', 'basic-tee'],
        )
