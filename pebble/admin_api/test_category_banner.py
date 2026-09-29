from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from products.models import Category


def uploaded_image(name, color):
    content = BytesIO()
    Image.new('RGB', (16, 16), color).save(content, 'PNG')
    return SimpleUploadedFile(name, content.getvalue(), content_type='image/png')


class CategoryBannerUploadTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='secret', is_staff=True)

    def test_owner_can_create_and_replace_category_banner_independently_of_tile(self):
        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            self.client.force_authenticate(self.owner)
            created = self.client.post('/api/admin/categories/', {
                'name': 'Clothing',
                'image': uploaded_image('tile.png', 'red'),
                'banner_image': uploaded_image('first-banner.png', 'blue'),
            }, format='multipart')
            self.assertEqual(created.status_code, 201, created.data)
            category = Category.objects.get(pk=created.data['id'])
            self.assertTrue(category.image.name.endswith('tile.png'))
            self.assertTrue(category.banner_image.name.endswith('first-banner.png'))

            changed = self.client.patch(f'/api/admin/categories/{category.id}/', {
                'banner_image': uploaded_image('new-banner.png', 'green'),
            }, format='multipart')
            self.assertEqual(changed.status_code, 200, changed.data)
            category.refresh_from_db()
            self.assertTrue(category.image.name.endswith('tile.png'))
            self.assertTrue(category.banner_image.name.endswith('new-banner.png'))

            self.client.force_authenticate(user=None)
            public = self.client.get('/api/products/categories/')
            self.assertEqual(public.status_code, 200)
            clothing = next(item for item in public.data if item['slug'] == 'clothing')
            self.assertTrue(clothing['banner_image'].endswith('new-banner.png'))

    def test_non_owner_cannot_change_banner(self):
        category = Category.objects.create(name='Clothing', slug='clothing')
        response = self.client.patch(f'/api/admin/categories/{category.id}/', {
            'banner_image': uploaded_image('private.png', 'red'),
        }, format='multipart')
        self.assertEqual(response.status_code, 401)
        category.refresh_from_db()
        self.assertFalse(category.banner_image)
