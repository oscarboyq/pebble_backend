from django.db import migrations


def enable_smart_collections(apps, schema_editor):
    """Sections bound to a smart collection should be driven by it, not by the
    legacy hand-picked category list."""
    MegaMenuSection = apps.get_model('home', 'MegaMenuSection')
    MegaMenuSection.objects.filter(
        smart_collection__isnull=False
    ).update(use_manual_categories=False)


def disable_smart_collections(apps, schema_editor):
    MegaMenuSection = apps.get_model('home', 'MegaMenuSection')
    MegaMenuSection.objects.filter(
        smart_collection__isnull=False
    ).update(use_manual_categories=True)


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0020_seed_smart_collections'),
    ]

    operations = [
        migrations.RunPython(enable_smart_collections, disable_smart_collections),
    ]
