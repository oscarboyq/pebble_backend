from django.db import migrations


# These are the product orders shown by the Pebble Little demo's two home tabs.
# Pins put them first without shrinking or replacing the underlying collections.
HOT_THIS_WEEK = {
    'best-sellers': {
        'sort': 'best_selling',
        'slugs': [
            'logo-polo-red', 'stripe-sun-hat', 'backpacks-kids',
            'stripe-backpack-brown', 'sleeveless-top', 'sport-shorts-navy',
            'straw-hat-beige', 'sneakers-green',
        ],
    },
    'new-arrivals': {
        'sort': 'newest',
        'slugs': [
            'basic-tee', 'fleece-jogger-pants', 'stripe-backpack-brown',
            'cuffed-shorts-khaki', 'leather-sandals-brown',
            'floral-pant-mint', 'wave-knit-top', 'sneakers-green',
        ],
    },
}


def curate_untouched_collections(apps, schema_editor):
    Collection = apps.get_model('collections', 'SmartCollection')
    Pin = apps.get_model('collections', 'SmartCollectionPin')
    Product = apps.get_model('products', 'Product')
    db = schema_editor.connection.alias

    for slug, config in HOT_THIS_WEEK.items():
        collection = Collection.objects.using(db).filter(slug=slug).first()
        if not collection or collection.collection_type != 'smart':
            continue
        if collection.sort != config['sort'] or collection.limit != 50:
            continue
        if collection.pins.exists() or collection.hides.exists() or collection.manual_products.exists():
            continue
        rules = list(collection.rules.values_list('field', 'operator', 'value'))
        if slug == 'best-sellers' and rules:
            continue
        if slug == 'new-arrivals' and rules != [('created_at', 'within_days', 30)]:
            continue

        products = dict(
            Product.objects.using(db).filter(slug__in=config['slugs'], is_active=True)
            .values_list('slug', 'id')
        )
        # An empty test database or an incomplete catalog must not get a
        # partially curated carousel. The migration can safely be a no-op.
        if len(products) != len(config['slugs']):
            continue
        Pin.objects.using(db).bulk_create([
            Pin(collection_id=collection.id, product_id=products[product_slug], position=index)
            for index, product_slug in enumerate(config['slugs'])
        ])


class Migration(migrations.Migration):
    dependencies = [
        ('collections', '0003_fill_clothing_collection'),
        ('products', '0018_fix_color_only_variants'),
    ]

    operations = [migrations.RunPython(curate_untouched_collections, migrations.RunPython.noop)]
