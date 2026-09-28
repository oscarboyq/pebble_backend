"""Preserve editorial links while adding typed relationships and seeded copy."""

from urllib.parse import urlparse

from django.db import migrations


def forwards(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    ProductImage = apps.get_model('products', 'ProductImage')
    ProductLink = apps.get_model('products', 'ProductLink')
    Collection = apps.get_model('collections', 'SmartCollection')
    LookbookCard = apps.get_model('home', 'LookbookCard')
    Hotspot = apps.get_model('home', 'LookbookHotspot')
    Marquee = apps.get_model('home', 'MarqueeItem')
    Trust = apps.get_model('home', 'TrustBadge')
    FooterSettings = apps.get_model('home', 'FooterSettings')
    FooterLink = apps.get_model('home', 'FooterLink')

    # The old many-to-many remains for current storefront clients and Django admin.
    # An unpositioned hotspot still belongs to the card's Shop the Look modal.
    for card in LookbookCard.objects.all().order_by('id'):
        ids = list(card.tagged_products.order_by('id').values_list('id', flat=True))
        for order, product_id in enumerate(ids):
            Hotspot.objects.get_or_create(card_id=card.id, product_id=product_id, defaults={'order': order})
        for source_id in ids:
            for order, target_id in enumerate(pid for pid in ids if pid != source_id):
                ProductLink.objects.get_or_create(source_id=source_id, target_id=target_id, intent='outfit', defaults={'order': order})

    Bundle = apps.get_model('home', 'ProductsBundleSection')
    for bundle in Bundle.objects.all():
        ids = list(bundle.bundle_products.order_by('id').values_list('id', flat=True))
        for source_id in ids:
            for order, target_id in enumerate(pid for pid in ids if pid != source_id):
                ProductLink.objects.get_or_create(source_id=source_id, target_id=target_id, intent='complementary', defaults={'order': order})

    # Keep every legacy URL verbatim; attach a typed target only when it resolves.
    destinations = {
        'BannerSlide': 'cta_link', 'CollectionsMenuLink': 'route',
        'CollectionsMenuPromo': 'route', 'NewInShowcaseCard': 'product_link',
        'OutfitHighlightItem': 'link_url', 'LayeredScrollingCard': 'link_url',
        'ProductsHighlightSection': 'button_link', 'OurStorySection': 'button_link',
        'BrandPillarItem': 'button_link', 'FlexCarouselCard': 'link',
        'ShopMenuPromo': 'cta_link', 'PagesMenuCard': 'route',
        'PagesMenuLink': 'route', 'FeaturesMenuItem': 'route',
        'FeaturesMenuSubItem': 'route',
    }
    for model_name, field in destinations.items():
        Model = apps.get_model('home', model_name)
        for item in Model.objects.all():
            path = urlparse(getattr(item, field) or '').path.strip('/')
            parts = path.split('/')
            if len(parts) != 2:
                continue
            if parts[0] == 'products':
                product = Product.objects.filter(slug=parts[1]).first()
                if product:
                    item.destination_product_id = product.id
                    item.save(update_fields=['destination_product'])
            elif parts[0] == 'collections':
                collection = Collection.objects.filter(slug=parts[1]).first()
                if collection:
                    item.destination_collection_id = collection.id
                    item.save(update_fields=['destination_collection'])

    # Existing primary flags and ordering are retained. Only blank alt text gets copy.
    for image in ProductImage.objects.filter(alt_text='').select_related('product'):
        image.alt_text = f'{image.product.name} product photo'
        image.save(update_fields=['alt_text'])

    for order, text in enumerate(['Comfort Products', 'PEBBLE', 'Organic Cotton', 'PEBBLE', 'Safety for Skin', 'PEBBLE']):
        Marquee.objects.create(text=text, order=order)
    for order, (icon, title, subtitle) in enumerate([
        ('delivery', 'Free delivery', 'In most US countries from $100'),
        ('returns', 'Free returns', 'Up to 30 days to return your items.'),
        ('payment', 'Payment 100% secured', 'Multiple payment options offered.'),
        ('service', 'Customer service', 'Monday-Friday: 9AM-4PM'),
    ]):
        Trust.objects.create(icon_key=icon, title=title, subtitle=subtitle, order=order)
    FooterSettings.objects.create(
        newsletter_heading='Subscribe for updates,\ntips & exclusive offers',
        newsletter_disclaimer='By subscribing you agree to the Terms of Use & Privacy Policy.',
        copyright_text='© 2026 Pebble Little, Powered by Shopify',
    )
    columns = {
        'company': [('Our Story', '/pages/our-story'), ('Contact', '/pages/contact'), ('FAQs', '/pages/faqs'), ('Blog', '/blogs/news'), ('Find a Store', '/pages/find-a-store')],
        'collection': [('Just Dropped', '/collections/just-dropped'), ('Best Sellers', '/collections/best-sellers'), ('Clothing', '/collections/clothing'), ('Pants', '/collections/pants'), ('Shirts', '/collections/shirts'), ('Jeans', '/collections/jeans')],
        'help': [('Help Center', '/pages/help-center'), ('Live Chat', '/pages/contact'), ('Return Policy', '/pages/returns-refunds'), ('Shipping Info', '/pages/orders-shipping'), ('Bulk Orders', '/pages/track-order')],
    }
    for column, links in columns.items():
        for order, (label, route) in enumerate(links):
            link = FooterLink(column=column, label=label, route=route, order=order)
            parts = route.strip('/').split('/')
            if len(parts) == 2 and parts[0] == 'collections':
                collection = Collection.objects.filter(slug=parts[1]).first()
                if collection:
                    link.collection_id = collection.id
            link.save()


class Migration(migrations.Migration):
    dependencies = [
        ('home', '0022_footersettings_marqueeitem_newslettersubscriber_and_more'),
        ('products', '0013_productlink'),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
