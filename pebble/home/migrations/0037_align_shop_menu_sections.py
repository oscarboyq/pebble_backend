from django.db import migrations


def align_shop_menu(apps, schema_editor):
    Section = apps.get_model('home', 'MegaMenuSection')
    Promo = apps.get_model('home', 'ShopMenuPromo')
    Collection = apps.get_model('collections', 'SmartCollection')

    for key in ('new_arrivals', 'best_sellers'):
        section = Section.objects.filter(key=key).first()
        if section and section.category_items.exists():
            Section.objects.filter(pk=section.pk).update(
                use_manual_categories=True,
                display_mode='categories',
            )

    clothing = Collection.objects.filter(slug='clothing').first()
    promo = Promo.objects.filter(
        section='clothing', cta_link='/products?category=clothing',
    ).first()
    if promo and clothing:
        Promo.objects.filter(pk=promo.pk).update(
            cta_link='/collections/clothing',
            destination_collection_id=clothing.pk,
            destination_product_id=None,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('home', '0036_seed_shop_menu_thumbnails'),
        ('collections', '0003_fill_clothing_collection'),
    ]
    operations = [migrations.RunPython(align_shop_menu, migrations.RunPython.noop)]
