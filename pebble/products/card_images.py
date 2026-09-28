"""Small, additive product images for collection cards.

Original uploads stay untouched. A missing derivative always falls back to the
original URL, so older records remain usable while the backfill runs.
"""

import hashlib
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


def card_image_name(product_image):
    if not product_image.pk or not product_image.images:
        return None
    digest = hashlib.sha1(product_image.images.name.encode('utf-8')).hexdigest()[:12]
    return f'product_card_images/{product_image.pk}-{digest}.webp'


def card_image_url(product_image):
    name = card_image_name(product_image)
    storage = product_image.images.storage
    return storage.url(name) if name and storage.exists(name) else None


def ensure_card_image(product_image, *, replace=False):
    """Generate a 640px WebP card image; return False for missing/invalid media."""
    name = card_image_name(product_image)
    if not name:
        return False
    storage = product_image.images.storage
    if storage.exists(name) and not replace:
        return True
    try:
        with product_image.images.open('rb') as source:
            with Image.open(source) as original:
                image = ImageOps.exif_transpose(original)
                image.thumbnail((640, 800), Image.Resampling.LANCZOS)
                if image.mode not in ('RGB', 'RGBA'):
                    image = image.convert('RGB')
                output = BytesIO()
                image.save(output, format='WEBP', quality=78, method=4)
    except (FileNotFoundError, OSError, UnidentifiedImageError, ValueError):
        return False
    if replace and storage.exists(name):
        storage.delete(name)
    storage.save(name, ContentFile(output.getvalue()))
    return True
