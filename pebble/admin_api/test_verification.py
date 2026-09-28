from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from home.models import MediaRightsRecord
from products.models import Category, Product, ProductImage


class OwnerVerificationTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='test', is_staff=True)
        category = Category.objects.create(name='T-Shirts', slug='t-shirts')
        self.product = Product.objects.create(
            category=category, name='Basic Tee', slug='basic-tee', price='20.00',
            material='100% Organic Cotton',
        )
        self.image = ProductImage.objects.create(
            product=self.product, images=SimpleUploadedFile('tee.jpg', b'local photo'),
        )

    def test_claim_is_hidden_until_owner_verifies_evidence_and_edit_resets_it(self):
        url = f'/api/products/{self.product.slug}/'
        self.assertEqual(self.client.get(url).data['material'], '')
        self.client.force_authenticate(self.owner)
        edit_url = f'/api/admin/products/{self.product.pk}/'
        self.assertEqual(self.client.get(edit_url).data['material'], '100% Organic Cotton')
        self.assertEqual(self.client.patch(edit_url, {'material_verified': True}, format='json').status_code, 400)
        result = self.client.patch(edit_url, {
            'material_source': 'Supplier label batch 2026-09', 'material_verified': True,
        }, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertTrue(result.data['material_verified'])
        self.assertEqual(self.client.get(url).data['material'], '100% Organic Cotton')
        self.client.patch(edit_url, {'material': 'Cotton blend'}, format='json')
        self.assertEqual(self.client.get(url).data['material'], '')
        self.assertFalse(Product.objects.get(pk=self.product.pk).material_verified_at)

    def test_media_rights_require_owner_and_evidence(self):
        url = '/api/admin/media-rights/'
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_authenticate(self.owner)
        inventory = self.client.get(url)
        self.assertEqual(inventory.status_code, 200)
        item = next(row for row in inventory.data if row['path'] == self.image.images.name)
        self.assertFalse(item['approved_for_public'])
        self.assertEqual(item['references'], 1)
        self.assertEqual(self.client.put(url, {'path': '../unreferenced.jpg'}, format='json').status_code, 400)
        self.assertEqual(self.client.put(url, {
            'path': self.image.images.name, 'approved_for_public': True,
        }, format='json').status_code, 400)
        self.assertEqual(MediaRightsRecord.objects.count(), 0)
        result = self.client.put(url, {
            'path': self.image.images.name,
            'rights_holder': 'Owner', 'permission_note': 'Written grant held offline',
            'approved_for_public': True,
        }, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        record = MediaRightsRecord.objects.get(path=self.image.images.name)
        self.assertEqual(record.reviewed_by, self.owner)
        self.assertTrue(record.approved_for_public)
