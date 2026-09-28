"""Complete the local Pebble demo gallery without replacing owner catalog data."""

from io import BytesIO
from urllib.parse import urlparse

import requests
from PIL import Image, UnidentifiedImageError
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from rest_framework.test import APIClient

from home.models import MediaRightsRecord
from products.models import Product


SOURCE = 'https://pebble-little.myshopify.com/products.json?limit=250'
MAX_IMAGE_BYTES = 15 * 1024 * 1024


class Command(BaseCommand):
    help = 'Complete existing demo product galleries via the owner image API. Dry run by default.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Upload missing images and record their source URLs.')
        parser.add_argument('--staff-id', type=int, help='Staff user ID used to authenticate owner API uploads.')

    def handle(self, *args, **options):
        try:
            response = requests.get(SOURCE, headers={'User-Agent': 'Pebble local catalog audit'}, timeout=30)
            response.raise_for_status()
            source_products = response.json()['products']
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise CommandError(f'Unable to read reference catalog: {exc}') from exc

        if len(source_products) != 53:
            raise CommandError(f'Expected 53 reference products; found {len(source_products)}. Audit changes before import.')
        local = {product.slug: product for product in Product.objects.filter(
            slug__in=[entry['handle'] for entry in source_products]
        ).prefetch_related('images')}
        missing_products = sorted({entry['handle'] for entry in source_products} - local.keys())
        if missing_products:
            raise CommandError(f'Reference products are missing locally: {missing_products}')

        planned = []
        existing = []
        for entry in source_products:
            product = local[entry['handle']]
            indexed = {image.order: image for image in product.images.all()}
            for index, source_image in enumerate(entry['images'], 1):
                source_url = source_image['src']
                parsed = urlparse(source_url)
                if parsed.scheme != 'https' or parsed.hostname != 'cdn.shopify.com':
                    raise CommandError(f'Unexpected image host for {product.slug} image {index}.')
                item = (product, index, source_url)
                (existing if index in indexed else planned).append(item)

        self.stdout.write(f'Reference: {len(source_products)} products, {len(existing) + len(planned)} photos')
        self.stdout.write(f'Already local: {len(existing)} photos; uploads needed: {len(planned)}')
        if not options['apply']:
            self.stdout.write('Dry run. Pass --apply to upload missing photos.')
            return

        staff_qs = get_user_model().objects.filter(is_staff=True, is_active=True)
        staff = staff_qs.filter(pk=options['staff_id']).first() if options['staff_id'] else staff_qs.order_by('pk').first()
        if staff is None:
            raise CommandError('An active staff account is required for owner API uploads.')
        client = APIClient(SERVER_NAME='localhost', SERVER_PORT='80')
        client.force_authenticate(user=staff)

        # Source metadata for the original first three photos is known from the
        # source image position. Never replace owner-entered rights details.
        for product, index, source_url in existing:
            image = next(image for image in product.images.all() if image.order == index)
            record, created = MediaRightsRecord.objects.get_or_create(
                path=image.images.name, defaults={'source_url': source_url}
            )
            if not created and not record.source_url:
                record.source_url = source_url
                record.save(update_fields=['source_url'])

        uploaded = 0
        for product, index, source_url in planned:
            # Recheck each row so interrupted runs can safely resume.
            current = product.images.filter(order=index).first()
            if current:
                MediaRightsRecord.objects.get_or_create(
                    path=current.images.name, defaults={'source_url': source_url}
                )
                continue
            try:
                image_response = requests.get(source_url, timeout=30)
                image_response.raise_for_status()
                content = image_response.content
                if len(content) > MAX_IMAGE_BYTES:
                    raise ValueError('image exceeds 15 MB')
                with Image.open(BytesIO(content)) as photo:
                    photo.verify()
                with Image.open(BytesIO(content)) as photo:
                    image_format = photo.format
                if image_format not in ('JPEG', 'PNG', 'WEBP'):
                    raise ValueError(f'unsupported image format {image_format}')
            except (requests.RequestException, UnidentifiedImageError, OSError, ValueError) as exc:
                raise CommandError(f'Cannot download {product.slug} image {index}: {exc}') from exc
            extension = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}[image_format]
            upload = SimpleUploadedFile(
                f'{product.slug}_{index}.{extension}', content,
                content_type={'jpg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}[extension],
            )
            result = client.post(
                f'/api/admin/products/{product.pk}/images/',
                {'image': upload, 'alt_text': f'{product.name} — view {index}',
                 'order': index, 'is_primary': 'false'},
                format='multipart',
            )
            if result.status_code != 201:
                detail = getattr(result, 'data', result.content[:300])
                raise CommandError(f'Owner API rejected {product.slug} image {index}: {result.status_code} {detail}')
            image = product.images.get(pk=result.data['id'])
            MediaRightsRecord.objects.get_or_create(
                path=image.images.name, defaults={'source_url': source_url}
            )
            uploaded += 1
            self.stdout.write(f'Uploaded {uploaded}/{len(planned)}: {product.slug} image {index}')
        self.stdout.write(self.style.SUCCESS(f'Finished: {uploaded} photos uploaded through the owner API.'))
