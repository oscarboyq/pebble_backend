from django.core.management.base import BaseCommand

from products.card_images import ensure_card_image
from products.models import ProductImage


class Command(BaseCommand):
    help = 'Build small collection-card WebP images without changing originals.'

    def add_arguments(self, parser):
        parser.add_argument('--replace', action='store_true')

    def handle(self, *args, **options):
        made = failed = 0
        for image in ProductImage.objects.iterator():
            if ensure_card_image(image, replace=options['replace']):
                made += 1
            else:
                failed += 1
        self.stdout.write(f'Card images available: {made}; missing or invalid originals: {failed}')
