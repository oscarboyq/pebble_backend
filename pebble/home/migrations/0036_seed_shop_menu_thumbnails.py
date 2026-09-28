from pathlib import Path

from django.conf import settings
from django.db import migrations


THUMBNAILS = {
    't-shirts': 'menu-shop-collection-1.jpg',
    'sets': 'menu-shop-collection-5.jpg',
    'sweaters': 'menu-shop-collection-2.jpg',
    'accessories': 'menu-shop-collection-6.jpg',
    'outerwear': 'menu-shop-collection-3.jpg',
    'shirts': 'menu-shop-collection-7.jpg',
    'pants': 'menu-shop-collection-4.jpg',
    'girls-shoes': 'menu-shop-collection-8.jpg',
}


def seed_existing_thumbnails(apps, schema_editor):
    MenuItem = apps.get_model('home', 'MegaMenuSectionCategory')
    for slug, filename in THUMBNAILS.items():
        path = f'category_images/{filename}'
        if not (Path(settings.MEDIA_ROOT) / path).is_file():
            continue
        MenuItem.objects.filter(
            section__key='new_arrivals', category__slug=slug,
            image_override__isnull=True,
        ).update(image_override=path)


class Migration(migrations.Migration):
    dependencies = [('home', '0035_megamenusectioncategory_image_override')]
    operations = [migrations.RunPython(seed_existing_thumbnails, migrations.RunPython.noop)]
