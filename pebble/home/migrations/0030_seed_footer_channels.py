from django.db import migrations


def seed_footer_channels(apps, schema_editor):
    FooterSettings = apps.get_model('home', 'FooterSettings')
    FooterLink = apps.get_model('home', 'FooterLink')
    for settings in FooterSettings.objects.all():
        if not settings.instagram_url:
            settings.instagram_url = 'https://instagram.com'
        if not settings.x_url:
            settings.x_url = 'https://x.com'
        if not settings.tiktok_url:
            settings.tiktok_url = 'https://tiktok.com'
        if not settings.pinterest_url:
            settings.pinterest_url = 'https://pinterest.com'
        settings.save(update_fields=['instagram_url', 'x_url', 'tiktok_url', 'pinterest_url'])
    for order, (label, route) in enumerate([
        ('Accessibility', '#'),
        ('Terms of Service', '/policies/terms-of-service'),
        ('Privacy Policy', '/policies/privacy-policy'),
    ]):
        FooterLink.objects.get_or_create(column='legal', label=label,
            defaults={'route': route, 'order': order})


class Migration(migrations.Migration):
    dependencies = [('home', '0029_footerinstagramimage_footersettings_instagram_handle_and_more')]
    operations = [migrations.RunPython(seed_footer_channels, migrations.RunPython.noop)]
