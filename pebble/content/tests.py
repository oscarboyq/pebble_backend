from django.test import TestCase
from rest_framework.test import APITestCase
from django.contrib.auth.models import User

from content.models import Page, Article
from merchandising.models import SmartCollection, SmartCollectionRule
from products.models import Category, Product, SizeChart


class ContentApiTests(APITestCase):
    def setUp(self):
        self.page = Page.objects.create(title='FAQs', slug='faqs', body='<p>Q&A</p>')
        Page.objects.create(title='Draft', slug='draft', body='x', is_published=False)
        self.article = Article.objects.create(
            title='Hello', slug='hello', excerpt='intro', body='<p>body</p>',
            blog_handle='news',
        )
        Article.objects.create(
            title='Hidden', slug='hidden', body='x', blog_handle='news', is_published=False,
        )

    def test_pages_list_only_published(self):
        resp = self.client.get('/api/pages/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([p['slug'] for p in resp.data], ['faqs'])

    def test_page_detail(self):
        resp = self.client.get('/api/pages/faqs/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['body'], '<p>Q&A</p>')
        self.assertEqual(self.client.get('/api/pages/missing/').status_code, 404)

    def test_articles_list_and_detail(self):
        listing = self.client.get('/api/blogs/news/')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([a['slug'] for a in listing.data], ['hello'])
        detail = self.client.get('/api/blogs/news/hello/')
        self.assertEqual(detail.status_code, 200)
        self.assertIn('body', detail.data)
        self.assertEqual(self.client.get('/api/blogs/news/nope/').status_code, 404)


class OwnerPageTests(APITestCase):
    def setUp(self):
        self.page = Page.objects.create(
            title='Shipping', slug='orders-shipping', body='<p>Old copy</p>'
        )
        self.staff = User.objects.create_user(
            'owner', password='ExamplePass123!', is_staff=True
        )
        self.buyer = User.objects.create_user('buyer', password='ExamplePass123!')

    def test_staff_edit_updates_public_page_without_changing_slug(self):
        self.client.force_authenticate(user=self.staff)
        listing = self.client.get('/api/admin/pages/')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data[0]['slug'], 'orders-shipping')
        changed = self.client.patch(
            f'/api/admin/pages/{self.page.pk}/',
            {'title': 'Orders & Shipping', 'body': '<p>Demo orders only.</p>',
             'slug': 'not-allowed', 'is_published': False},
            format='json',
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.data['slug'], 'orders-shipping')
        self.assertTrue(changed.data['is_published'])
        self.client.force_authenticate(user=None)
        public = self.client.get('/api/pages/orders-shipping/')
        self.assertEqual(public.data['body'], '<p>Demo orders only.</p>')

    def test_buyer_cannot_edit_and_published_page_cannot_be_empty(self):
        self.client.force_authenticate(user=self.buyer)
        denied = self.client.patch(
            f'/api/admin/pages/{self.page.pk}/', {'body': 'new'}, format='json'
        )
        self.assertEqual(denied.status_code, 403)
        self.client.force_authenticate(user=self.staff)
        invalid = self.client.patch(
            f'/api/admin/pages/{self.page.pk}/', {'body': '  '}, format='json'
        )
        self.assertEqual(invalid.status_code, 400)


class SearchApiTests(APITestCase):
    def setUp(self):
        cat = Category.objects.create(name='T-Shirts', slug='t-shirts', gender='all')
        Product.objects.create(category=cat, name='Basic Tee', slug='basic-tee', price='20.00')
        Page.objects.create(title='Tee Size Guide', slug='tee-size', body='x')
        SmartCollection.objects.create(name='Tees', slug='tees')
        Article.objects.create(title='Tee trends', slug='tee-trends', excerpt='tee', blog_handle='news')

    def test_search_groups(self):
        resp = self.client.get('/api/search/', {'q': 'tee'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['products']), 1)
        self.assertEqual(len(resp.data['collections']), 1)
        self.assertEqual(len(resp.data['pages']), 1)
        self.assertEqual(len(resp.data['articles']), 1)

    def test_empty_query_returns_empty_groups(self):
        resp = self.client.get('/api/search/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['products'], [])


class SizeChartApiTests(APITestCase):
    def test_returns_null_when_absent(self):
        resp = self.client.get('/api/products/size-chart/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data)

    def test_returns_first_active_chart(self):
        SizeChart.objects.create(
            name='Kids', columns=['Size', 'Chest'], rows=[['3Y', '53']], is_active=True
        )
        resp = self.client.get('/api/products/size-chart/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['columns'], ['Size', 'Chest'])
        self.assertEqual(resp.data['rows'], [['3Y', '53']])


class CollectionIndexTests(APITestCase):
    def setUp(self):
        cat = Category.objects.create(name='Shirts', slug='shirts', gender='boys')
        Product.objects.create(category=cat, name='Shirt', slug='shirt', price='20.00')
        self.collection = SmartCollection.objects.create(
            name='Shirts', slug='shirts-col', is_featured=True
        )
        SmartCollectionRule.objects.create(
            collection=self.collection, field='category', operator='in', value=['shirts']
        )

    def test_index_reports_product_count(self):
        resp = self.client.get('/api/collections/')
        self.assertEqual(resp.status_code, 200)
        row = next(c for c in resp.data if c['slug'] == 'shirts-col')
        self.assertEqual(row['product_count'], 1)
        self.assertTrue(row['is_featured'])

    def test_featured_filter(self):
        SmartCollection.objects.create(name='Other', slug='other', is_featured=False)
        resp = self.client.get('/api/collections/', {'featured': 'true'})
        self.assertEqual({c['slug'] for c in resp.data}, {'shirts-col'})
