from django.db import migrations

# Demo values captured on 2026-09-28; the seven local-only products are inferred.
# Owners can correct merchandising labels in Flutter admin.
PRODUCT_TYPES = {'backpacks-kids': 'Backpacks',
 'basic-tee': 'T-Shirts',
 'basic-tee-brown-1': 'Shirts',
 'bucket-hat-green': 'Hats',
 'campus-spirit-e-cap': 'Hats',
 'canvas-sneaker': 'Shoes',
 'cargo-pants': 'Pants',
 'chino-shorts-beige': 'Pants',
 'colorblock-backpack': 'Backpacks',
 'colorblock-jacket': 'Jackets',
 'cotton-polo': 'Shirts',
 'cotton-polo-green': 'Shirts',
 'cotton-shirt-lilac': 'Shirts',
 'crochet-tank-aqua': 'Tank Tops',
 'crochet-tank-mint': 'Tank Tops',
 'cuffed-shorts-khaki': 'Shorts',
 'denim-jeans-kids': 'Hoodies',
 'denim-shorts-blue': 'Dresses',
 'denim-shorts-blue-1': 'Shirts',
 'drawstring-shorts': 'Shorts',
 'fleece-hoodie-beige': 'Hoodies',
 'fleece-hoodie-kids': 'Hoodies',
 'fleece-jogger-pants': 'Pants',
 'floral-knit-mint': 'Pants',
 'floral-pant-mint': 'Pants',
 'gingham-dress-blue': 'Dresses',
 'green-shorts-kids': 'Hats',
 'kids-sneakers-green': 'Shoes',
 'knit-beanie-kids': 'Beanies',
 'knit-sweater-red': 'Sweaters',
 'leather-sandals-brown': 'Shoes',
 'light-jacket-grey': 'Jackets',
 'linen-shorts': 'Shorts',
 'linen-vest-cream': 'Vests',
 'logo-polo-red': 'Shirts',
 'mini-backpack-pink': 'Backpacks',
 'pleated-skirt-kids': 'Skirts',
 'pocket-vest': 'Vests',
 'print-tee-green': 'T-Shirts',
 'puffer-jacket': 'Jackets',
 'puffer-vest-kids': 'Jackets',
 'rib-tee': 'T-Shirts',
 'sleeveless-top': 'Tank Tops',
 'sneakers-green': 'Shoes',
 'sneakers-green-hw': 'Shoes',
 'sport-shorts-navy': 'Shorts',
 'straw-hat-beige': 'Hats',
 'stripe-backpack-brown': 'Backpacks',
 'stripe-beanie-brown': 'Backpacks',
 'stripe-polo-pink': 'Sweaters',
 'stripe-shorts': 'Shorts',
 'stripe-sun-hat': 'Hats',
 'stripe-tee': 'T-Shirts',
 'striped-knit-bag': 'Bags',
 'striped-shorts': 'Pants',
 'sweatpants-kids': 'Pants',
 'varsity-jacket-blue': 'Jackets',
 'velcro-sneaker': 'Shoes',
 'wave-knit-top': 'Tank Tops',
 'wrap-jacket-cream': 'Jackets'}


def seed_types(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    for slug, product_type in PRODUCT_TYPES.items():
        Product.objects.filter(slug=slug, product_type='').update(product_type=product_type)


class Migration(migrations.Migration):
    dependencies = [('products', '0016_product_type')]
    operations = [migrations.RunPython(seed_types, migrations.RunPython.noop)]
