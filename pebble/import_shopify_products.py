import os
import re
import json
import socket
import requests
from decimal import Decimal
import django

socket.setdefaulttimeout(10)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pebble.settings')
django.setup()

from django.conf import settings
from products.models import Product, Category, ProductImage, ProductVariant


def clean_html(raw_html):
    if not raw_html:
        return ''
    clean = re.sub(r'<[^>]+>', ' ', raw_html)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()


def get_category_slug(p):
    ptype = p.get('product_type', '')
    title = p.get('title', '')
    
    if ptype == 'Dresses':
        return 'girls-dresses'
    if ptype == 'Skirts':
        return 'girls-skirts'
    if ptype == 'Bags':
        return 'girls-bags'
    if ptype == 'Backpacks':
        if 'pink' in title.lower() or 'mini' in title.lower():
            return 'girls-bags'
        return 'accessories'
    if ptype == 'Beanies':
        return 'girls-accessories'
    if ptype == 'Hats':
        if any(w in title.lower() for w in ['straw', 'bucket', 'beige']):
            return 'girls-accessories'
        return 'accessories'
    if ptype == 'Shoes':
        if 'sandal' in title.lower():
            return 'sandals'
        return 'girls-shoes'
    if ptype in ['Sweaters', 'Hoodies']:
        if any(w in title.lower() for w in ['pink', 'beige', 'wrap']):
            return 'girls-sweaters'
        return 'sweaters'
    if ptype in ['Jackets', 'Vests']:
        if any(w in title.lower() for w in ['wrap', 'cream']):
            return 'girls-outerwear'
        if any(w in title.lower() for w in ['vest']):
            return 'outerwear'
        return 'coats-jackets'
    if ptype == 'Pants':
        return 'pants'
    if ptype == 'Shorts':
        return 'shorts'
    if ptype == 'Shirts':
        return 'shirts'
    if ptype in ['T-Shirts', 'Tank Tops']:
        return 't-shirts'
    return 'clothing'


def get_badge(tags):
    for tag in tags or []:
        t = str(tag).strip().lower()
        if t == 'hot':
            return 'Hot'
        if t == 'popular':
            return 'Popular'
        if t == 'new':
            return 'New'
    return ''


def download_image(url, dest_path):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000:
        return True
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8, stream=True)
        if r.status_code == 200:
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=32768):
                    if chunk:
                        f.write(chunk)
            if os.path.getsize(dest_path) > 100:
                return True
            else:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
    except Exception as e:
        print(f"    Warning: Failed to download {url}: {e}")
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass
    return False


def run():
    print("=" * 60)
    print("Fetching products from Pebble Shopify reference store...")
    print("=" * 60)

    url = 'https://pebble-little.myshopify.com/products.json?limit=250'
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    sp_products = resp.json()['products']

    print(f"Found {len(sp_products)} products on reference site.\n")

    media_dir = os.path.join(settings.MEDIA_ROOT, 'product_images')
    os.makedirs(media_dir, exist_ok=True)

    imported_count = 0
    updated_count = 0

    for i, sp in enumerate(sp_products, 1):
        title = sp['title'].strip()
        handle = sp['handle'].strip()
        body_html = sp.get('body_html', '')
        description = clean_html(body_html) or f"High-quality {title} designed for kids by Pebble."
        tags = sp.get('tags', [])
        badge = get_badge(tags)
        cslug = get_category_slug(sp)

        try:
            category = Category.objects.get(slug=cslug)
        except Category.DoesNotExist:
            print(f"Warning: Category slug {cslug} not found! Defaulting to accessories.")
            category = Category.objects.first()

        variants = sp.get('variants', [])
        first_variant = variants[0] if variants else {}
        price = Decimal(first_variant.get('price', '30.00'))
        raw_compare = first_variant.get('compare_at_price')
        compare_at_price = Decimal(raw_compare) if raw_compare else None
        sku = first_variant.get('sku') or f"PEB-{handle[:12].upper()}"

        # Check existing product by handle/slug or name
        product = Product.objects.filter(slug=handle).first()
        if not product:
            product = Product.objects.filter(name__iexact=title).first()

        if product:
            product.name = title
            product.slug = handle
            product.category = category
            product.description = description
            product.price = price
            product.compare_at_price = compare_at_price
            product.badge = badge
            product.sku = sku
            product.is_active = True
            product.material = '100% Organic Cotton'
            product.care_and_cleaning = 'Machine wash cold, gentle cycle with like colors. Tumble dry low or line dry.'
            product.manufactured_by = 'Pebble Studios'
            product.save()
            updated_count += 1
            action = "UPDATED"
        else:
            # Check unique slug
            final_slug = handle
            count = 1
            while Product.objects.filter(slug=final_slug).exists():
                final_slug = f"{handle}-{count}"
                count += 1

            product = Product.objects.create(
                name=title,
                slug=final_slug,
                category=category,
                description=description,
                price=price,
                compare_at_price=compare_at_price,
                badge=badge,
                sku=sku,
                is_active=True,
                material='100% Organic Cotton',
                care_and_cleaning='Machine wash cold, gentle cycle with like colors. Tumble dry low or line dry.',
                manufactured_by='Pebble Studios',
            )
            imported_count += 1
            action = "CREATED"

        print(f"[{i:2d}/{len(sp_products)}] {action}: '{title}' -> Category: {category.name} ({category.slug}, {category.gender}) | Price: ${price}")

        # Download & sync images (first 3 images)
        images = sp.get('images', [])
        if images:
            # If product has no images or outdated images, sync
            product.images.all().delete()
            for img_idx, img in enumerate(images[:3], 1):
                src = img['src']
                ext = 'jpg'
                if '.png' in src.lower():
                    ext = 'png'
                elif '.webp' in src.lower():
                    ext = 'webp'
                filename = f"{product.slug}_{img_idx}.{ext}"
                dest = os.path.join(media_dir, filename)
                
                success = download_image(src, dest)
                if success:
                    rel_path = f"product_images/{filename}"
                    ProductImage.objects.create(
                        product=product,
                        images=rel_path,
                        alt_text=f"{product.name} view {img_idx}",
                        is_primary=(img_idx == 1),
                        order=img_idx,
                    )

        # Sync variants
        if variants:
            product.variants.all().delete()
            for v_idx, v in enumerate(variants, 1):
                v_title = v.get('title', '')
                opt1 = v.get('option1')
                opt2 = v.get('option2')
                v_price = Decimal(v.get('price', str(price)))
                p_override = v_price if v_price != price else None
                v_sku = v.get('sku') or f"{sku}-{v_idx}"

                color = ''
                size = ''
                if opt1 and opt2:
                    color = str(opt1)
                    size = str(opt2)
                elif opt1:
                    if any(c in str(opt1).lower() for c in ['cm', 'y', 'm', 'xs', 's', 'l', 'xl']):
                        size = str(opt1)
                    else:
                        color = str(opt1)

                ProductVariant.objects.create(
                    product=product,
                    color=color,
                    size=size,
                    stock=50,
                    price_override=p_override,
                    attributes={'title': v_title, 'option1': opt1, 'option2': opt2},
                )

    print("\n" + "=" * 60)
    print("Updating category display counts to match real active products...")
    print("=" * 60)
    for c in Category.objects.all().order_by('gender', 'name'):
        real_count = c.products.filter(is_active=True).count()
        c.display_count = real_count
        c.save(update_fields=['display_count'])
        print(f"Category: {c.name:<18} (slug: {c.slug:<18}, gender: {c.gender:<6}) -> {real_count} real products")

    print("\n" + "=" * 60)
    print(f"COMPLETED! Created: {imported_count}, Updated: {updated_count}, Total Shopify Products: {len(sp_products)}")
    print("=" * 60)


if __name__ == '__main__':
    run()
