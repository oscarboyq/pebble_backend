from django.db import migrations


def forwards(apps, schema_editor):
    Collection = apps.get_model('collections', 'SmartCollection')
    collection, _ = Collection.objects.get_or_create(
        slug='all', defaults={
            'name': 'All Products', 'description': 'Explore the complete collection.',
            'collection_type': 'smart', 'sort': 'newest', 'limit': 60,
            'position': 1000, 'is_active': True,
        }
    )
    for model_name, link_field in [
        ('BannerSlide', 'cta_link'), ('LayeredScrollingCard', 'link_url'),
        ('BrandPillarItem', 'button_link'), ('FlexCarouselCard', 'link'),
    ]:
        Model = apps.get_model('home', model_name)
        Model.objects.filter(**{link_field: '/collections/all'}, destination_collection__isnull=True).update(
            destination_collection_id=collection.id
        )


class Migration(migrations.Migration):
    dependencies = [('home', '0023_catalog_content_data')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
