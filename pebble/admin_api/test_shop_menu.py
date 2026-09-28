from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from home.models import MegaMenuSection, MegaMenuSectionCategory
from products.models import Category


class ShopMenuOwnerTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user('shop_owner', password='test', is_staff=True)
        self.section = MegaMenuSection.objects.create(
            key='new_arrivals', title='New Arrivals', use_manual_categories=True,
        )
        self.tee = Category.objects.create(name='T-Shirts', slug='t-shirts')
        self.sets = Category.objects.create(name='Sets', slug='sets')
        self.base = f'/api/admin/mega-menu-sections/{self.section.id}/categories/'

    def test_owner_thumbnail_survives_category_reorder_and_reaches_public_menu(self):
        self.assertEqual(self.client.put(self.base, {'category_ids': [self.tee.id]} , format='json').status_code, 401)
        self.client.force_authenticate(self.owner)
        saved = self.client.put(self.base, {
            'category_ids': [self.tee.id, self.sets.id],
        }, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        image_url = f'{self.base}{self.tee.id}/image/'
        changed = self.client.patch(image_url, {
            'image': SimpleUploadedFile('tee.jpg', b'menu thumbnail', content_type='image/jpeg'),
        }, format='multipart')
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertIn('/media/menu_category_images/tee', changed.data['categories'][0]['image_override'])
        reordered = self.client.put(self.base, {
            'category_ids': [self.sets.id, self.tee.id],
        }, format='json')
        self.assertEqual(reordered.status_code, 200, reordered.data)
        self.assertEqual(reordered.data['categories'][1]['id'], self.tee.id)
        self.assertIsNotNone(reordered.data['categories'][1]['image_override'])
        self.assertEqual(MegaMenuSectionCategory.objects.filter(section=self.section).count(), 2)
        self.assertEqual(self.client.put(self.base, {
            'category_ids': [self.tee.id, self.tee.id],
        }, format='json').status_code, 400)
        self.client.force_authenticate(user=None)
        public = self.client.get('/api/home/').data['shop_menu']['new_arrivals']['categories']
        self.assertEqual([category['slug'] for category in public], ['sets', 't-shirts'])
        self.assertIn('/media/menu_category_images/tee', public[1]['image'])

    def test_owner_can_clear_menu_thumbnail_without_changing_category_cover(self):
        self.client.force_authenticate(self.owner)
        self.client.put(self.base, {'category_ids': [self.tee.id]}, format='json')
        image_url = f'{self.base}{self.tee.id}/image/'
        self.client.patch(image_url, {
            'image': SimpleUploadedFile('tee.jpg', b'menu thumbnail', content_type='image/jpeg'),
        }, format='multipart')
        cleared = self.client.patch(image_url, {'clear_image': True}, format='json')
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertIsNone(cleared.data['categories'][0]['image_override'])
