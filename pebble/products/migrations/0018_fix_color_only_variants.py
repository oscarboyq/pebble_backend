from django.db import migrations


COLOR_ONLY_PRODUCTS = {
    'canvas-sneaker', 'velcro-sneaker', 'green-shorts-kids',
    'knit-beanie-kids', 'kids-sneakers-green', 'stripe-sun-hat',
    'colorblock-backpack', 'straw-hat-beige',
}


def move_color_option(apps, schema_editor):
    Variant = apps.get_model('products', 'ProductVariant')
    for variant in Variant.objects.filter(
        product__slug__in=COLOR_ONLY_PRODUCTS, color='',
    ):
        if variant.size:
            variant.color = variant.size
            variant.size = ''
            variant.save(update_fields=['color', 'size'])


class Migration(migrations.Migration):
    dependencies = [('products', '0017_seed_product_types')]
    operations = [migrations.RunPython(move_color_option, migrations.RunPython.noop)]
