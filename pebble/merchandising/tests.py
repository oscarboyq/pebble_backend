from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from orders.models import Order, OrderItem
from products.models import Category, Product, ProductVariant, Review, Tag

from merchandising.models import (
    SmartCollection,
    SmartCollectionManualProduct,
    SmartCollectionHide,
    SmartCollectionPin,
    SmartCollectionRule,
)
from merchandising.services import engine


class EngineTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.boys = Category.objects.create(name='Boys', slug='boys', gender='boys')
        cls.girls = Category.objects.create(name='Girls', slug='girls', gender='girls')

        cls.p1 = Product.objects.create(
            category=cls.boys, name='P1', slug='p1', price=Decimal('10.00'), badge='New',
        )
        cls.p2 = Product.objects.create(
            category=cls.boys, name='P2', slug='p2', price=Decimal('30.00'),
            compare_at_price=Decimal('40.00'),
        )
        cls.p3 = Product.objects.create(
            category=cls.girls, name='P3', slug='p3', price=Decimal('50.00'),
        )

        ProductVariant.objects.create(product=cls.p1, color='red', size='S', stock=5)
        ProductVariant.objects.create(product=cls.p2, color='red', size='S', stock=0)

        tag = Tag.objects.create(name='Organic', slug='organic')
        cls.p1.tags.add(tag)

        cls.user = User.objects.create_user(username='u1', password='x')
        Review.objects.create(product=cls.p3, user=cls.user, rating=5)

    def make_collection(self, rules=None, **kwargs):
        collection = SmartCollection.objects.create(
            name=kwargs.pop('name', 'C'),
            slug=kwargs.pop('slug', 'c'),
            **kwargs,
        )
        for index, rule in enumerate(rules or []):
            SmartCollectionRule.objects.create(
                collection=collection, order=index, **rule,
            )
        return collection

    def slugs(self, queryset):
        return set(queryset.values_list('slug', flat=True))


class RuleTests(EngineTestBase):
    def test_within_days(self):
        old = Product.objects.create(
            category=self.boys, name='Old', slug='old', price=Decimal('5.00'),
        )
        Product.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )
        collection = self.make_collection(
            rules=[{'field': 'created_at', 'operator': 'within_days', 'value': 30}]
        )
        self.assertNotIn('old', self.slugs(engine.resolve(collection)))

    def test_price_gte(self):
        collection = self.make_collection(
            rules=[{'field': 'price', 'operator': 'gte', 'value': 30}]
        )
        self.assertEqual(self.slugs(engine.resolve(collection)), {'p2', 'p3'})

    def test_category_in(self):
        collection = self.make_collection(
            rules=[{'field': 'category', 'operator': 'in', 'value': ['girls']}]
        )
        self.assertEqual(self.slugs(engine.resolve(collection)), {'p3'})

    def test_gender_eq(self):
        collection = self.make_collection(
            rules=[{'field': 'gender', 'operator': 'eq', 'value': 'boys'}]
        )
        self.assertEqual(self.slugs(engine.resolve(collection)), {'p1', 'p2'})

    def test_in_stock_true(self):
        collection = self.make_collection(
            rules=[{'field': 'in_stock', 'operator': 'eq', 'value': True}]
        )
        self.assertEqual(self.slugs(engine.resolve(collection)), {'p1'})

    def test_in_stock_false(self):
        collection = self.make_collection(
            rules=[{'field': 'in_stock', 'operator': 'eq', 'value': False}]
        )
        self.assertEqual(self.slugs(engine.resolve(collection)), {'p2', 'p3'})

    def test_on_sale_true(self):
        collection = self.make_collection(
            rules=[{'field': 'on_sale', 'operator': 'eq', 'value': True}]
        )
        self.assertEqual(self.slugs(engine.resolve(collection)), {'p2'})

    def test_on_sale_false(self):
        collection = self.make_collection(
            rules=[{'field': 'on_sale', 'operator': 'eq', 'value': False}]
        )
        self.assertEqual(self.slugs(engine.resolve(collection)), {'p1', 'p3'})

    def test_badge_eq(self):
        collection = self.make_collection(
            rules=[{'field': 'badge', 'operator': 'eq', 'value': 'New'}]
        )
        self.assertEqual(self.slugs(engine.resolve(collection)), {'p1'})

    def test_tag_in(self):
        collection = self.make_collection(
            rules=[{'field': 'tag', 'operator': 'in', 'value': ['organic']}]
        )
        self.assertEqual(self.slugs(engine.resolve(collection)), {'p1'})

    def test_rating_gte(self):
        collection = self.make_collection(
            rules=[{'field': 'rating', 'operator': 'gte', 'value': 4}]
        )
        self.assertEqual(self.slugs(engine.resolve(collection)), {'p3'})

    def test_match_any(self):
        collection = self.make_collection(
            match_mode='any',
            rules=[
                {'field': 'badge', 'operator': 'eq', 'value': 'New'},
                {'field': 'category', 'operator': 'in', 'value': ['girls']},
            ],
        )
        self.assertEqual(self.slugs(engine.resolve(collection)), {'p1', 'p3'})

    def test_match_all(self):
        collection = self.make_collection(
            match_mode='all',
            rules=[
                {'field': 'price', 'operator': 'gte', 'value': 30},
                {'field': 'category', 'operator': 'in', 'value': ['girls']},
            ],
        )
        self.assertEqual(self.slugs(engine.resolve(collection)), {'p3'})


class CollectionBehaviourTests(EngineTestBase):
    def test_hidden_excluded(self):
        collection = self.make_collection(
            rules=[{'field': 'price', 'operator': 'gte', 'value': 0}]
        )
        SmartCollectionHide.objects.create(collection=collection, product=self.p2)
        self.assertEqual(self.slugs(engine.resolve(collection)), {'p1', 'p3'})

    def test_pins_first(self):
        collection = self.make_collection(
            rules=[{'field': 'price', 'operator': 'gte', 'value': 0}],
            sort='price_asc',
        )
        SmartCollectionPin.objects.create(
            collection=collection, product=self.p3, position=0,
        )
        ordered = list(engine.resolve(collection).values_list('slug', flat=True))
        self.assertEqual(ordered[0], 'p3')

    def test_manual_collection_order(self):
        collection = self.make_collection(
            collection_type='manual', sort='manual',
        )
        SmartCollectionManualProduct.objects.create(
            collection=collection, product=self.p3, position=0,
        )
        SmartCollectionManualProduct.objects.create(
            collection=collection, product=self.p1, position=1,
        )
        ordered = list(engine.resolve(collection).values_list('slug', flat=True))
        self.assertEqual(ordered, ['p3', 'p1'])

    def test_sort_price_desc(self):
        collection = self.make_collection(
            rules=[{'field': 'price', 'operator': 'gte', 'value': 0}],
            sort='price_desc',
        )
        ordered = list(engine.resolve(collection).values_list('slug', flat=True))
        self.assertEqual(ordered, ['p3', 'p2', 'p1'])

    def test_sort_best_selling(self):
        order = Order.objects.create(
            user=self.user, status='confirmed', full_name='x', phone='1',
            address_line1='a', city='c', state='s', postal_code='1',
            total_amount=Decimal('300.00'),
        )
        OrderItem.objects.create(
            order=order, product=self.p2, quantity=10,
            unit_price=Decimal('30.00'), line_total=Decimal('300.00'),
        )
        collection = self.make_collection(
            rules=[{'field': 'price', 'operator': 'gte', 'value': 0}],
            sort='best_selling',
        )
        ordered = list(engine.resolve(collection).values_list('slug', flat=True))
        self.assertEqual(ordered[0], 'p2')


class PreviewTests(EngineTestBase):
    def test_preview_count_and_limit(self):
        total, products = engine.preview(
            [{'field': 'price', 'operator': 'gte', 'value': 0}],
            match_mode='all', sort='newest', limit=2,
        )
        self.assertEqual(total, 3)
        self.assertEqual(len(products), 2)

    def test_preview_manual(self):
        total, products = engine.preview(
            [], manual_product_ids=[self.p1.id, self.p3.id],
            sort='manual', limit=10,
        )
        self.assertEqual(total, 2)
        self.assertEqual({p.slug for p in products}, {'p1', 'p3'})
