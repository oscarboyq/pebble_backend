from django.db import migrations


COPY = {
    'Free delivery': ('In most US countries from $100', 'Browse freely', 'Explore the local catalog and curated looks.'),
    'Free returns': ('Up to 30 days to return your items.', 'Clear totals', 'Review cart pricing before checkout.'),
    'Payment 100% secured': ('Multiple payment options offered.', 'Demo checkout', 'Orders are recorded without payment.'),
    'Customer service': ('Monday-Friday: 9AM-4PM', 'Owner curated', 'Stories and product pairings are editable.'),
}


def update_badges(apps, schema_editor):
    TrustBadge = apps.get_model('home', 'TrustBadge')
    MarqueeItem = apps.get_model('home', 'MarqueeItem')
    CollectionsMenuLink = apps.get_model('home', 'CollectionsMenuLink')
    for old_title, (old_subtitle, new_title, new_subtitle) in COPY.items():
        TrustBadge.objects.filter(title=old_title, subtitle=old_subtitle).update(
            title=new_title, subtitle=new_subtitle
        )
    MarqueeItem.objects.filter(text='Organic Cotton').update(text='Everyday Comfort')
    MarqueeItem.objects.filter(text='Safety for Skin').update(text='Made for Play')
    CollectionsMenuLink.objects.filter(
        label='Organic Cotton', route='/products?search=organic'
    ).update(label='Everyday Essentials', route='/products')


def restore_badges(apps, schema_editor):
    TrustBadge = apps.get_model('home', 'TrustBadge')
    MarqueeItem = apps.get_model('home', 'MarqueeItem')
    CollectionsMenuLink = apps.get_model('home', 'CollectionsMenuLink')
    for old_title, (old_subtitle, new_title, new_subtitle) in COPY.items():
        TrustBadge.objects.filter(title=new_title, subtitle=new_subtitle).update(
            title=old_title, subtitle=old_subtitle
        )
    MarqueeItem.objects.filter(text='Everyday Comfort').update(text='Organic Cotton')
    MarqueeItem.objects.filter(text='Made for Play').update(text='Safety for Skin')
    CollectionsMenuLink.objects.filter(
        label='Everyday Essentials', route='/products'
    ).update(label='Organic Cotton', route='/products?search=organic')


class Migration(migrations.Migration):
    dependencies = [('home', '0031_repair_local_navigation')]
    operations = [migrations.RunPython(update_badges, restore_badges)]
