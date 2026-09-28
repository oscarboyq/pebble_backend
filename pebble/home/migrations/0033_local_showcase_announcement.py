from django.db import migrations


OLD = 'Free shipping on all orders over 5 · Code: PEBBLE25'
NEW = 'Explore the Pebble Little local showcase · No payment collected'


def update_announcement(apps, schema_editor):
    PromoBar = apps.get_model('home', 'PromoBar')
    StoreSettings = apps.get_model('home', 'StoreSettings')
    PromoBar.objects.filter(text=OLD).update(text=NEW)
    StoreSettings.objects.filter(promo_bar_text=OLD).update(promo_bar_text=NEW)


def restore_announcement(apps, schema_editor):
    PromoBar = apps.get_model('home', 'PromoBar')
    StoreSettings = apps.get_model('home', 'StoreSettings')
    PromoBar.objects.filter(text=NEW).update(text=OLD)
    StoreSettings.objects.filter(promo_bar_text=NEW).update(promo_bar_text=OLD)


class Migration(migrations.Migration):
    dependencies = [('home', '0032_local_showcase_trust_copy')]
    operations = [migrations.RunPython(update_announcement, restore_announcement)]
