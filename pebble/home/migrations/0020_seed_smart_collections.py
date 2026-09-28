from django.db import migrations


def seed(apps, schema_editor):
    SmartCollection = apps.get_model('collections', 'SmartCollection')
    SmartCollectionRule = apps.get_model('collections', 'SmartCollectionRule')
    MegaMenuSection = apps.get_model('home', 'MegaMenuSection')

    new_arrivals, _ = SmartCollection.objects.get_or_create(
        slug='new-arrivals',
        defaults={
            'name': 'New Arrivals',
            'collection_type': 'smart',
            'match_mode': 'all',
            'sort': 'newest',
            'limit': 50,
            'is_active': True,
        },
    )
    if not new_arrivals.rules.exists():
        SmartCollectionRule.objects.create(
            collection=new_arrivals,
            field='created_at',
            operator='within_days',
            value=30,
            order=0,
        )

    best_sellers, _ = SmartCollection.objects.get_or_create(
        slug='best-sellers',
        defaults={
            'name': 'Best Sellers',
            'collection_type': 'smart',
            'match_mode': 'all',
            'sort': 'best_selling',
            'limit': 50,
            'is_active': True,
        },
    )

    for key, collection in (
        ('new_arrivals', new_arrivals),
        ('best_sellers', best_sellers),
    ):
        MegaMenuSection.objects.filter(
            key=key, smart_collection__isnull=True
        ).update(smart_collection=collection)


def unseed(apps, schema_editor):
    MegaMenuSection = apps.get_model('home', 'MegaMenuSection')
    SmartCollection = apps.get_model('collections', 'SmartCollection')

    MegaMenuSection.objects.filter(
        key__in=['new_arrivals', 'best_sellers']
    ).update(smart_collection=None)
    SmartCollection.objects.filter(
        slug__in=['new-arrivals', 'best-sellers']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0019_megamenusection_display_mode_and_more'),
        ('collections', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
