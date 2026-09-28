from django.db import migrations


COPY = {
    'contact': (
        '<p>Email us at happytohelp@pebble.com. We reply within one business day.</p>',
        '<p>Contact details for this local showcase will be provided by the store owner before public launch.</p>',
    ),
    'faqs': (
        '<p><strong>How long does shipping take?</strong> 3-7 business days.</p><p><strong>What is your return policy?</strong> 30-day free returns.</p>',
        '<p><strong>Will I be charged?</strong> No. Checkout records a local demonstration order without taking payment.</p><p><strong>Will an order ship?</strong> No shipping is arranged for this showcase.</p>',
    ),
    'find-a-store': (
        '<p>Our flagship store is open Monday to Saturday, 9AM-6PM.</p>',
        '<p>No physical store is listed for this local showcase.</p>',
    ),
    'help-center': (
        '<p>Answers to common questions about orders, shipping and returns.</p>',
        '<p>This showcase records demonstration orders without payment or shipping. Store help details will be published before a public launch.</p>',
    ),
    'orders-shipping': (
        '<p>Orders ship within 24 hours. Tracking is emailed at dispatch.</p>',
        '<p>Orders placed in this local showcase are for demonstration. No shipping or fulfillment is arranged.</p>',
    ),
    'privacy-policy': (
        '<p>We respect your privacy and never sell your data.</p>',
        '<p>This local showcase stores account and order information for testing. A complete privacy policy requires owner review before any public launch.</p>',
    ),
    'returns-refunds': (
        '<p>Return any unused item within 30 days for a full refund.</p>',
        '<p>This local showcase does not collect payment or ship orders. A return and refund policy will be provided before a public launch.</p>',
    ),
    'secure-payment': (
        '<p>All transactions are encrypted and PCI-compliant.</p>',
        '<p>This local showcase does not take payment. Checkout records a demonstration order only.</p>',
    ),
    'size-guide': (
        '<p>Measure chest, waist and hips, then match to the size chart below.</p>',
        '<p>Check the size information on each product before selecting a variant. Full sizing guidance requires owner review.</p>',
    ),
    'terms-of-service': (
        '<p>By using this store you agree to our terms of service.</p>',
        '<p>This local showcase is for evaluation. Orders are recorded without payment or fulfillment. Public store terms require owner review.</p>',
    ),
    'track-order': (
        '<p>Enter your order number and email to track your parcel.</p>',
        '<p>Sign in and open Orders to view your local demonstration orders. Parcel tracking is not available.</p>',
    ),
}


def replace_demo_claims(apps, schema_editor):
    Page = apps.get_model('content', 'Page')
    for slug, (old, new) in COPY.items():
        Page.objects.filter(slug=slug, body=old).update(body=new)


def restore_demo_claims(apps, schema_editor):
    Page = apps.get_model('content', 'Page')
    for slug, (old, new) in COPY.items():
        Page.objects.filter(slug=slug, body=new).update(body=old)


class Migration(migrations.Migration):
    dependencies = [('content', '0001_initial')]
    operations = [migrations.RunPython(replace_demo_claims, restore_demo_claims)]
