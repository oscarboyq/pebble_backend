from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from PIL import Image
from rest_framework.test import APITestCase

from home.models import ProductSuggestionSection, ProductSuggestionStep, NewsletterSubscriber, NewInShowcaseSettings
from products.models import Category, Product, ProductImage, SizeChart
from merchandising.models import SmartCollection
from admin_api.catalog_content_views import EDITORIAL_MODELS


class OwnerContentTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='test', is_staff=True)
        self.category = Category.objects.create(name='T-Shirts', slug='t-shirts')
        self.product = Product.objects.create(category=self.category, name='Basic Tee', slug='basic-tee', price='20.00')

    def test_schema_and_suggestion_visibility_reach_public_home(self):
        self.assertEqual(self.client.get('/api/admin/home/content/suggestion-steps/schema/').status_code, 401)
        self.client.force_authenticate(self.owner)
        schema = self.client.get('/api/admin/home/content/suggestion-steps/schema/')
        self.assertEqual(schema.status_code, 200)
        self.assertIn('products', {field['name'] for field in schema.data['fields']})
        section = ProductSuggestionSection.objects.create(heading='Style in steps')
        response = self.client.post('/api/admin/home/content/suggestion-steps/', {
            'section': section.id, 'step_number': 1, 'title': 'Choose a tee',
            'products': [self.product.id], 'is_active': True,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        step = ProductSuggestionStep.objects.get(pk=response.data['id'])
        self.assertEqual(list(step.products.values_list('id', flat=True)), [self.product.id])
        self.client.force_authenticate(user=None)
        public = self.client.get('/api/home/').data
        self.assertEqual(public['product_suggestion']['steps'][0]['title'], 'Choose a tee')
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.patch(f'/api/admin/home/content/suggestion-steps/{step.id}/',
            {'is_active': False}, format='json').status_code, 200)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get('/api/home/').data['product_suggestion']['steps'], [])

    def test_new_in_button_collection_is_owner_editable(self):
        outerwear = SmartCollection.objects.create(name='Outerwear', slug='outerwear')
        settings, _ = NewInShowcaseSettings.objects.get_or_create(pk=1)
        self.client.force_authenticate(self.owner)
        schema = self.client.get('/api/admin/home/content/new-in-settings/schema/')
        self.assertEqual(schema.status_code, 200)
        self.assertIn('destination_collection', {field['name'] for field in schema.data['fields']})
        saved = self.client.patch(
            f'/api/admin/home/content/new-in-settings/{settings.id}/',
            {'destination_collection': outerwear.id, 'button_text': 'Shop Now'},
            format='json',
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(saved.data['cta_link'], '/collections/outerwear')
        self.client.force_authenticate(user=None)
        public = self.client.get('/api/home/').data['new_in_showcase_settings']
        self.assertEqual(public['cta_link'], '/collections/outerwear')
        self.assertEqual(public['destination_collection_id'], outerwear.id)

    def test_every_owner_section_has_a_readable_editor_contract(self):
        self.client.force_authenticate(self.owner)
        edited = 0
        for kind in EDITORIAL_MODELS:
            with self.subTest(kind=kind):
                list_response = self.client.get(f'/api/admin/home/content/{kind}/')
                schema_response = self.client.get(f'/api/admin/home/content/{kind}/schema/')
                self.assertEqual(list_response.status_code, 200)
                self.assertEqual(schema_response.status_code, 200)
                self.assertTrue(schema_response.data['fields'])
                if list_response.data:
                    item = list_response.data[0]
                    field = next((name for name in ('is_active', 'order', 'title',
                        'heading', 'label', 'name', 'text', 'who_we_are_title')
                        if name in item), None)
                    self.assertIsNotNone(field)
                    saved = self.client.patch(
                        f"/api/admin/home/content/{kind}/{item['id']}/",
                        {field: item[field]}, format='json')
                    self.assertEqual(saved.status_code, 200, saved.data)
                    edited += 1
        self.assertGreaterEqual(edited, 5)

    def test_product_image_metadata_and_collection_cover(self):
        self.client.force_authenticate(self.owner)
        first = ProductImage.objects.create(product=self.product, images='product_images/first.jpg', is_primary=True)
        second = ProductImage.objects.create(product=self.product, images='product_images/second.jpg')
        response = self.client.patch(f'/api/admin/products/{self.product.id}/images/{second.id}/',
            {'alt_text': 'Basic Tee front', 'order': 1, 'is_primary': True}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        first.refresh_from_db(); second.refresh_from_db()
        self.assertFalse(first.is_primary)
        self.assertTrue(second.is_primary)
        self.assertEqual(second.alt_text, 'Basic Tee front')
        self.assertEqual(second.order, 1)
        self.assertEqual(self.client.patch(
            f'/api/admin/products/{self.product.id}/images/{first.id}/',
            {'is_primary': False}, format='json').status_code, 200)
        second.refresh_from_db()
        self.assertTrue(second.is_primary)
        collection = SmartCollection.objects.create(name='T-Shirts', slug='t-shirts')
        upload = SimpleUploadedFile('cover.jpg', b'cover-bytes', content_type='image/jpeg')
        response = self.client.patch(f'/api/admin/collections/{collection.id}/',
            {'description': 'Soft tees', 'is_featured': 'true', 'image': upload}, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        collection.refresh_from_db()
        self.assertEqual(collection.description, 'Soft tees')
        self.assertTrue(collection.is_featured)
        self.assertTrue(collection.image.name.startswith('collections/cover'))

    def test_size_chart_validation_and_subscriber_status(self):
        self.client.force_authenticate(self.owner)
        path = '/api/admin/home/content/size-charts/'
        bad = self.client.post(path, {'name': 'Kids', 'columns': ['Size', 'Chest'],
            'rows': [['4Y']]}, format='json')
        self.assertEqual(bad.status_code, 400)
        good = self.client.post(path, {'name': 'Kids', 'columns': ['Size', 'Chest'],
            'rows': [['4Y', '24 in']], 'is_active': True}, format='json')
        self.assertEqual(good.status_code, 201, good.data)
        self.assertTrue(SizeChart.objects.filter(name='Kids').exists())
        subscriber = NewsletterSubscriber.objects.create(email='parent@example.com')
        response = self.client.patch('/api/admin/home/newsletter-subscribers/',
            {'id': subscriber.id, 'is_active': False}, format='json')
        self.assertEqual(response.status_code, 200)
        subscriber.refresh_from_db()
        self.assertFalse(subscriber.is_active)

    def test_owner_uploads_footer_image_for_public_footer(self):
        self.client.force_authenticate(self.owner)
        stream = BytesIO()
        Image.new('RGB', (2, 2), '#c99484').save(stream, format='PNG')
        upload = SimpleUploadedFile('footer.png', stream.getvalue(), content_type='image/png')
        response = self.client.post('/api/admin/home/content/footer-instagram-images/',
            {'image': upload, 'alt_text': 'Pebble outfit', 'order': 0}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        self.client.force_authenticate(user=None)
        images = self.client.get('/api/home/').data['footer_instagram_images']
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]['alt_text'], 'Pebble outfit')
