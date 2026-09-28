from django.db import migrations


APPAREL_CATEGORIES = [
    'coats-jackets',
    'outerwear',
    'pants',
    'sets',
    'shirts',
    'shorts',
    'sweaters',
    't-shirts',
    'girls-dresses',
    'girls-outerwear',
    'girls-skirts',
    'girls-sweaters',
]


def fill_clothing(apps, schema_editor):
    Rule = apps.get_model('collections', 'SmartCollectionRule')
    for rule in Rule.objects.filter(
        collection__slug='clothing', field='category', operator='in'
    ):
        if rule.value == ['clothing']:
            rule.value = APPAREL_CATEGORIES
            rule.save(update_fields=['value'])


class Migration(migrations.Migration):
    dependencies = [
        ('collections', '0002_alter_smartcollection_options_and_more'),
        ('home', '0031_repair_local_navigation'),
    ]

    operations = [migrations.RunPython(fill_clothing, migrations.RunPython.noop)]
