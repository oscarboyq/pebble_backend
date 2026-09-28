"""Idempotent seed for storefront content: static pages, blog articles,
a size chart, and a SmartCollection per product category.

Usage: ``python manage.py seed_content``
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from content.models import Page, Article
from merchandising.models import SmartCollection, SmartCollectionRule
from products.models import Category, SizeChart


PAGES = [
    ('Our Story', 'our-story',
     '<p>We create simple, well-made essentials that balance comfort and style, '
     'giving kids the freedom to explore, play, and grow every day.</p>'),
    ('FAQs', 'faqs',
     '<p><strong>How long does shipping take?</strong> 3-7 business days.</p>'
     '<p><strong>What is your return policy?</strong> 30-day free returns.</p>'),
    ('Contact Us', 'contact',
     '<p>Email us at happytohelp@pebble.com. We reply within one business day.</p>'),
    ('Find A Store', 'find-a-store',
     '<p>Our flagship store is open Monday to Saturday, 9AM-6PM.</p>'),
    ('Our Journal', 'our-journal',
     '<p>Stories from the studio: design notes, styling tips and more.</p>'),
    ('Help Center', 'help-center',
     '<p>Answers to common questions about orders, shipping and returns.</p>'),
    ('Size Guide', 'size-guide',
     '<p>Measure chest, waist and hips, then match to the size chart below.</p>'),
    ('Returns & Refunds', 'returns-refunds',
     '<p>Return any unused item within 30 days for a full refund.</p>'),
    ('Orders & Shipping', 'orders-shipping',
     '<p>Orders ship within 24 hours. Tracking is emailed at dispatch.</p>'),
    ('Track Order', 'track-order',
     '<p>Enter your order number and email to track your parcel.</p>'),
    ('Secure Payment', 'secure-payment',
     '<p>All transactions are encrypted and PCI-compliant.</p>'),
    ('Terms of Service', 'terms-of-service',
     '<p>By using this store you agree to our terms of service.</p>'),
    ('Privacy Policy', 'privacy-policy',
     '<p>We respect your privacy and never sell your data.</p>'),
    ('Accessibility', 'accessibility',
     '<p>We are committed to making our store accessible to everyone.</p>'),
]

ARTICLES = [
    ('Child on pink structure', 'child-on-pink-structure',
     'How playful shapes and soft palettes come together in our latest drop.'),
    ('Our Creative Director\u2019s Date', 'our-creative-directors-date',
     'A behind-the-scenes look at the inspiration for this season.'),
    ('Through the eyes of the designer', 'through-the-eyes-of-the-designer',
     'Design notes on comfort, colour and everyday play.'),
    ('Pink Style for Kids', 'pink-style-for-kids',
     'Three ways to style our favourite pink pieces.'),
    ('Soft Kidswear Tones', 'soft-kidswear-tones',
     'Why muted, natural tones are a wardrobe staple.'),
]

SIZE_CHART_COLUMNS = ['Size', 'Chest (cm)', 'Waist (cm)', 'Hips (cm)']
SIZE_CHART_ROWS = [
    ['3Y', '53', '50', '56'],
    ['4Y', '56', '52', '59'],
    ['5Y', '58', '54', '62'],
    ['6Y', '61', '56', '65'],
    ['7Y', '63', '58', '68'],
    ['8Y', '66', '60', '71'],
]


class Command(BaseCommand):
    help = 'Seed storefront pages, blog articles, size chart and collections.'

    def handle(self, *args, **options):
        page_created = self._seed_pages()
        article_created = self._seed_articles()
        chart_created = self._seed_size_chart()
        collection_created = self._seed_collections()

        self.stdout.write(self.style.SUCCESS(
            f'seed_content complete: {page_created} pages, '
            f'{article_created} articles, {chart_created} size charts, '
            f'{collection_created} collections created.'
        ))

    def _seed_pages(self):
        created = 0
        for title, slug, body in PAGES:
            _, was_created = Page.objects.get_or_create(
                slug=slug, defaults={'title': title, 'body': body}
            )
            created += 1 if was_created else 0
        return created

    def _seed_articles(self):
        created = 0
        now = timezone.now()
        for index, (title, slug, excerpt) in enumerate(ARTICLES):
            _, was_created = Article.objects.get_or_create(
                slug=slug,
                defaults={
                    'title': title,
                    'excerpt': excerpt,
                    'body': f'<p>{excerpt}</p>',
                    'author_name': 'Pebble Studio',
                    'published_at': now - timezone.timedelta(days=index),
                },
            )
            created += 1 if was_created else 0
        return created

    def _seed_size_chart(self):
        chart, was_created = SizeChart.objects.get_or_create(
            name='Kids apparel',
            defaults={
                'columns': SIZE_CHART_COLUMNS,
                'rows': SIZE_CHART_ROWS,
                'note': 'How to measure: 1. Chest  2. Waist  3. Low hip.',
            },
        )
        return 1 if was_created else 0

    def _seed_collections(self):
        created = 0
        for index, category in enumerate(Category.objects.all().order_by('id')):
            collection, was_created = SmartCollection.objects.get_or_create(
                slug=category.slug,
                defaults={
                    'name': category.name,
                    'description': f'Shop our {category.name.lower()} collection.',
                    'collection_type': SmartCollection.TYPE_SMART,
                    'sort': SmartCollection.SORT_NEWEST,
                    'limit': 50,
                    'is_featured': category.is_featured,
                    'position': index,
                },
            )
            if was_created:
                created += 1
                SmartCollectionRule.objects.get_or_create(
                    collection=collection,
                    field=SmartCollectionRule.FIELD_CATEGORY,
                    operator=SmartCollectionRule.OP_IN,
                    defaults={'value': [category.slug], 'order': 0},
                )
        return created
