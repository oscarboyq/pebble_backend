from django.db import migrations


def forwards(apps, schema_editor):
    HeaderMenuItem = apps.get_model('home', 'HeaderMenuItem')
    for order, (key, label) in enumerate([
        ('shop', 'Shop'), ('collections', 'Collections'),
        ('pages', 'Pages'), ('features', 'Features'),
    ]):
        HeaderMenuItem.objects.get_or_create(key=key, defaults={'label': label, 'order': order})


class Migration(migrations.Migration):
    dependencies = [('home', '0025_headermenuitem')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
