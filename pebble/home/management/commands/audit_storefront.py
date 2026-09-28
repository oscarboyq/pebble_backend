"""Read-only audit of media files and owner-managed storefront destinations."""

import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, FileField

from admin_api.catalog_content_views import LINK_FIELDS
from content.models import Article, Page
from merchandising.models import SmartCollection
from merchandising.services import engine
from products.models import Category, Product, ProductImage
from home.models import MediaRightsRecord


def destination_issue(raw):
    value = (raw or '').strip()
    if not value:
        return None
    if value == '#':
        return 'placeholder destination'
    parsed = urlsplit(value)
    if parsed.scheme in ('http', 'https', 'mailto'):
        return None
    if parsed.scheme or not value.startswith('/'):
        return 'unsupported destination'
    path = parsed.path.rstrip('/') or '/'
    parts = path.strip('/').split('/') if path != '/' else []
    query = parse_qs(parsed.query)
    if not parts:
        return None
    if parts[0] == 'products':
        if len(parts) == 2:
            return None if Product.objects.filter(slug=parts[1], is_active=True).exists() else 'missing product'
        if len(parts) == 1:
            categories = query.get('category', [])
            if categories and not Category.objects.filter(slug=categories[0]).exists():
                return 'missing category'
            return None
    if parts[0] == 'collections':
        if len(parts) == 1:
            return None
        if len(parts) == 2:
            return None if SmartCollection.objects.filter(slug=parts[1], is_active=True).exists() else 'missing collection'
    if parts[0] in ('pages', 'policies') and len(parts) == 2:
        return None if Page.objects.filter(slug=parts[1], is_published=True).exists() else 'missing page'
    if parts[0] == 'blogs' and len(parts) in (2, 3):
        matches = Article.objects.filter(blog_handle=parts[1], is_published=True)
        if len(parts) == 3:
            matches = matches.filter(slug=parts[2])
        return None if matches.exists() else 'missing blog content'
    if path in ('/search', '/cart', '/checkout', '/login', '/register', '/wishlist', '/orders', '/profile'):
        return None
    return 'unknown storefront route'


class Command(BaseCommand):
    help = 'Audit local media references and owner-managed storefront links without changing data.'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='Write JSON report to this path.')
        parser.add_argument('--inventory', help='Write referenced media inventory with unverified provenance.')
        parser.add_argument('--strict', action='store_true', help='Exit nonzero when a media file or link is broken.')

    def handle(self, *args, **options):
        media_checked = 0
        missing_media = []
        media_inventory = []
        rights = {record.path: record for record in MediaRightsRecord.objects.all()}
        for model in apps.get_models():
            fields = [field for field in model._meta.fields if isinstance(field, FileField)]
            if not fields:
                continue
            for row in model.objects.all().iterator():
                for field in fields:
                    file = getattr(row, field.name)
                    if not file or not file.name:
                        continue
                    media_checked += 1
                    media_inventory.append({
                        'model': model.__name__, 'id': row.pk,
                        'field': field.name, 'name': file.name,
                        'provenance': 'owner-approved' if rights.get(file.name) and rights[file.name].approved_for_public else 'unverified',
                    })
                    if not file.storage.exists(file.name):
                        missing_media.append({
                            'model': model.__name__, 'id': row.pk,
                            'field': field.name, 'name': file.name,
                        })

        links_checked = 0
        broken_links = []
        for model, field_name in LINK_FIELDS.items():
            for row in model.objects.all().iterator():
                if hasattr(row, 'is_active') and not row.is_active:
                    continue
                value = getattr(row, field_name, '')
                if not value:
                    continue
                links_checked += 1
                issue = destination_issue(value)
                if issue:
                    broken_links.append({
                        'model': model.__name__, 'id': row.pk,
                        'field': field_name, 'value': value, 'issue': issue,
                    })
        result = {
            'media_checked': media_checked,
            'missing_media': missing_media,
            'unique_media_without_owner_approval': len({item['name'] for item in media_inventory if item['provenance'] == 'unverified'}),
            'links_checked': links_checked,
            'broken_links': broken_links,
            'empty_active_collections': [
                collection.slug for collection in SmartCollection.objects.filter(is_active=True)
                if not engine.filtered_queryset(collection).exists()
            ],
            'product_images_missing_alt': ProductImage.objects.filter(alt_text='').count(),
            'active_products_without_variants': list(
                Product.objects.filter(is_active=True)
                .annotate(variant_count=Count('variants'))
                .filter(variant_count=0)
                .order_by('slug')
                .values_list('slug', flat=True)
            ),
            'published_pages_under_200_characters': [
                page.slug for page in Page.objects.filter(is_published=True)
                if len(page.body.strip()) < 200
            ],
            'unverified_organic_material_claims': list(
                Product.objects.filter(
                    is_active=True, material__iexact='100% Organic Cotton', material_verified_at__isnull=True
                ).order_by('slug').values_list('slug', flat=True)
            ),
        }
        rendered = json.dumps(result, indent=2)
        if options['output']:
            Path(options['output']).write_text(rendered + '\n', encoding='utf-8')
        if options['inventory']:
            Path(options['inventory']).write_text(
                json.dumps(media_inventory, indent=2) + '\n', encoding='utf-8'
            )
        self.stdout.write(rendered)
        if options['strict'] and (missing_media or broken_links or result['empty_active_collections']):
            raise CommandError('Storefront audit found broken media, links, or empty active collections.')
