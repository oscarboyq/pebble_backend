from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase
from PIL import Image

from .models import Product, Category, ProductImage, ProductVariant, Review, Tag


class ProductsPhase1Tests(APITestCase):
    def setUp(self):
        self.cat_a = Category.objects.create(name='Shirts', slug='shirts', gender='boys')
        self.cat_b = Category.objects.create(name='Shoes', slug='shoes', gender='all')
        self.tag_new = Tag.objects.create(name='New', slug='new')
        self.tag_hot = Tag.objects.create(name='Hot', slug='hot')

        self.p1 = self._make_product('Polo Red', 'polo-red', self.cat_a, tags=[self.tag_new])
        self.p2 = self._make_product('Denim Shirt', 'denim-shirt', self.cat_a, tags=[self.tag_hot])
        self.p3 = self._make_product('Runner', 'runner', self.cat_b)

        self.user = User.objects.create_user(
            username='buyer@example.com', email='buyer@example.com', password='x'
        )
        Review.objects.create(product=self.p1, user=self.user, rating=5, title='Great', is_approved=True)
        other = User.objects.create_user(username='other@example.com', email='other@example.com', password='x')
        Review.objects.create(product=self.p1, user=other, rating=1, title='Hidden', is_approved=False)

    def _make_product(self, name, slug, category, tags=None, price='20.00', compare=None, badge=''):
        product = Product.objects.create(
            category=category, name=name, slug=slug, description='desc',
            price=Decimal(price), compare_at_price=Decimal(compare) if compare else None,
            badge=badge,
        )
        ProductVariant.objects.create(product=product, color='Blue', size='3Y', stock=5)
        if tags:
            product.tags.set(tags)
        return product

    # ── serializer fields ────────────────────────────────────────────────
    def test_product_payload_exposes_tags_rating_and_stock(self):
        resp = self.client.get(f'/api/products/{self.p1.slug}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('tags', resp.data)
        self.assertIn('rating', resp.data)
        self.assertIn('review_count', resp.data)
        self.assertIn('in_stock', resp.data)
        self.assertIn('total_stock', resp.data)
        self.assertEqual(resp.data['rating'], 5.0)          # unapproved review ignored
        self.assertEqual(resp.data['review_count'], 1)
        self.assertEqual(resp.data['total_stock'], 5)
        self.assertTrue(resp.data['in_stock'])
        self.assertEqual([t['slug'] for t in resp.data['tags']], ['new'])

    def test_card_image_is_smaller_and_original_remains_available(self):
        original = BytesIO()
        Image.new('RGB', (1500, 1800), '#b66b73').save(original, 'PNG')
        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            image = ProductImage.objects.create(
                product=self.p1,
                images=SimpleUploadedFile('tee.png', original.getvalue(), content_type='image/png'),
                is_primary=True,
            )
            response = self.client.get(f'/api/products/{self.p1.slug}/')
            self.assertEqual(response.status_code, 200)
            media = response.data['images'][0]
            self.assertTrue(media['image'].endswith('.png'))
            self.assertTrue(media['card_image'].endswith('.webp'))
            with image.images.open('rb') as source:
                self.assertEqual(Image.open(source).size, (1500, 1800))
            from .card_images import card_image_name
            with image.images.storage.open(card_image_name(image), 'rb') as card:
                self.assertLessEqual(Image.open(card).size[0], 640)

    def test_review_list_only_shows_approved(self):
        resp = self.client.get(f'/api/products/{self.p1.slug}/reviews/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['rating'], 5)

    # ── filtering ────────────────────────────────────────────────────────
    def test_tag_filter(self):
        resp = self.client.get('/api/products/', {'tag': 'hot'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([p['slug'] for p in resp.data], ['denim-shirt'])

    # ── pagination (opt-in) ──────────────────────────────────────────────
    def test_plain_list_is_backwards_compatible(self):
        resp = self.client.get('/api/products/')
        self.assertIsInstance(resp.data, list)
        self.assertIn('X-Total-Count', resp)

    def test_opt_in_pagination_returns_envelope(self):
        resp = self.client.get('/api/products/', {'page': 1, 'page_size': 2})
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(set(['count', 'page', 'page_size', 'results']), set(resp.data.keys()))
        self.assertGreaterEqual(resp.data['count'], 3)
        self.assertEqual(len(resp.data['results']), 2)

    def test_paginated_newest_order_has_stable_tie_breaker(self):
        same_time = self.p1.created_at
        Product.objects.filter(pk__in=[self.p2.pk, self.p3.pk]).update(
            created_at=same_time,
        )
        slugs = []
        for page in (1, 2, 3):
            response = self.client.get('/api/products/', {
                'page': page, 'page_size': 1, 'sort': 'newest',
            })
            self.assertEqual(response.status_code, 200)
            slugs.extend(item['slug'] for item in response.data['results'])
        self.assertEqual(slugs, ['runner', 'denim-shirt', 'polo-red'])

    # ── facets ───────────────────────────────────────────────────────────
    def test_facets_endpoint(self):
        resp = self.client.get('/api/products/facets/', {'category': 'shirts'})
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        for key in ('total', 'availability', 'price', 'colors', 'sizes', 'categories', 'tags', 'sort_options'):
            self.assertIn(key, data)
        self.assertEqual(data['total'], 2)
        colors = {c['value']: c['count'] for c in data['colors']}
        self.assertEqual(colors.get('Blue'), 2)
        self.assertEqual({t['value'] for t in data['tags']}, {'new', 'hot'})

    def test_product_type_is_distinct_from_category_and_owner_editable(self):
        self.p1.product_type = 'Polos'
        self.p1.save(update_fields=['product_type'])
        self.p2.product_type = 'Shirts'
        self.p2.save(update_fields=['product_type'])
        facets = self.client.get('/api/products/facets/', {'category': 'shirts'})
        self.assertEqual(
            {item['value']: item['count'] for item in facets.data['product_types']},
            {'Polos': 1, 'Shirts': 1},
        )
        response = self.client.get('/api/products/', {'product_type': 'Polos'})
        self.assertEqual([item['slug'] for item in response.data], ['polo-red'])

        staff = User.objects.create_user('owner', password='x', is_staff=True)
        self.client.force_authenticate(staff)
        edited = self.client.patch(
            f'/api/admin/products/{self.p1.pk}/',
            {'product_type': 'T-Shirts'}, format='json',
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.data['product_type'], 'T-Shirts')

    # ── related products ─────────────────────────────────────────────────
    def test_related_prefers_same_category_and_excludes_self(self):
        resp = self.client.get(f'/api/products/{self.p1.slug}/related/', {'limit': 5})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['intent'], 'related')
        slugs = [p['slug'] for p in resp.data['products']]
        self.assertNotIn(self.p1.slug, slugs)
        self.assertEqual(slugs[0], 'denim-shirt')  # same category first

    def test_complementary_intent_shape(self):
        resp = self.client.get(f'/api/products/{self.p1.slug}/related/', {'intent': 'complementary'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['intent'], 'complementary')
        self.assertNotIn(self.p1.slug, [p['slug'] for p in resp.data['products']])


class AdminTagApiTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='admin@example.com', email='admin@example.com',
            password='x', is_staff=True,
        )
        self.client.force_authenticate(self.staff)
        self.cat = Category.objects.create(name='Shirts', slug='shirts', gender='boys')

    def test_tag_crud(self):
        create = self.client.post('/api/admin/tags/', {'name': 'Popular'}, format='json')
        self.assertEqual(create.status_code, 201)
        tag_id = create.data['id']

        listing = self.client.get('/api/admin/tags/')
        self.assertEqual(listing.status_code, 200)
        self.assertTrue(any(t['id'] == tag_id for t in listing.data))

        patch = self.client.patch(f'/api/admin/tags/{tag_id}/', {'name': 'Trending'}, format='json')
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(patch.data['name'], 'Trending')

        delete = self.client.delete(f'/api/admin/tags/{tag_id}/')
        self.assertEqual(delete.status_code, 204)

    def test_create_product_with_tags_and_relation(self):
        resp = self.client.post('/api/admin/products/', {
            'category_id': self.cat.id,
            'name': 'Tagged Tee',
            'price': '19.00',
            'tags': [{'name': 'New'}, {'name': 'Hot'}],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual({t['slug'] for t in resp.data['tags']}, {'new', 'hot'})

        product_id = resp.data['id']
        patch = self.client.patch(f'/api/admin/products/{product_id}/', {
            'tags': ['Pop'],
        }, format='json')
        self.assertEqual(patch.status_code, 200, patch.data)
        self.assertEqual([t['slug'] for t in patch.data['tags']], ['pop'])
