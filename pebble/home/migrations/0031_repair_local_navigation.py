from django.db import migrations


def repair_links(apps, schema_editor):
    Collection = apps.get_model('collections', 'SmartCollection')
    Product = apps.get_model('products', 'Product')

    menu = apps.get_model('home', 'CollectionsMenuLink')
    for old, new, label, target in [
        ('/products?category=legging', '/collections/pants', 'Pants', 'pants'),
        ('/products?category=knitwear', '/collections/sweaters', 'Sweaters', 'sweaters'),
        ('/products?category=dresses', '/collections/girls-dresses', 'Dresses', 'girls-dresses'),
        ('/products?category=jeans', '/collections/pants', 'Pants', 'pants'),
    ]:
        matches = menu.objects.filter(
            route=old,
            destination_product__isnull=True,
            destination_collection__isnull=True,
        )
        destination = Collection.objects.filter(slug=target).first()
        if destination:
            matches.update(route=new, label=label, destination_collection=destination)

    promo = apps.get_model('home', 'CollectionsMenuPromo')
    promo.objects.filter(route='/collections/summer-sale').update(route='/products?sale=true')
    destination = Collection.objects.filter(slug='all').first()
    if destination:
        promo.objects.filter(
        route='/collections/talkative-child',
        destination_product__isnull=True,
        destination_collection__isnull=True,
        ).update(route='/collections/all', destination_collection=destination)

    feature = apps.get_model('home', 'FeaturesMenuSubItem')
    destination = Collection.objects.filter(slug='clothing').first()
    if destination:
        feature.objects.filter(
        route='/collections/boy-s-clothing',
        destination_product__isnull=True,
        destination_collection__isnull=True,
        ).update(route='/collections/clothing', destination_collection=destination)

    footer = apps.get_model('home', 'FooterLink')
    destination = Collection.objects.filter(slug='new-arrivals').first()
    if destination:
        footer.objects.filter(
        route='/collections/just-dropped',
        product__isnull=True,
        collection__isnull=True,
        ).update(route='/collections/new-arrivals', collection=destination)
    destination_product = Product.objects.filter(slug='denim-jeans-kids').first()
    if destination_product:
        footer.objects.filter(
        route='/collections/jeans',
        product__isnull=True,
        collection__isnull=True,
        ).update(route='/products/denim-jeans-kids', product=destination_product)
    footer.objects.filter(column='legal', label='Accessibility', route='#').update(
        route='/pages/accessibility'
    )


class Migration(migrations.Migration):
    dependencies = [('home', '0030_seed_footer_channels')]

    operations = [migrations.RunPython(repair_links, migrations.RunPython.noop)]
