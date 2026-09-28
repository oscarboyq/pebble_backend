"""Exercise owner product curation through buyer checkout, then roll back."""

import json
import argparse
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pebble.settings')

import django
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIRequestFactory, force_authenticate

from admin_api.catalog_content_views import AdminProductLinksView
from cart.views import CartItemAddView, CartView
from cart.views import CartBundleAddView
from home.models import ProductsBundleSection
from orders.models import Order
from orders.views import PlaceOrderView
from products.models import Product, ProductLink, ProductVariant
from products.views import ProductDetailView, ProductListView, ProductRelatedView


factory = APIRequestFactory(HTTP_HOST='localhost')
arguments = argparse.ArgumentParser()
arguments.add_argument('--output', default='PHASE6_WALKTHROUGH.json')
options = arguments.parse_args()


def request(view, method, path, *, user=None, data=None, kwargs=None):
    builder = getattr(factory, method.lower())
    incoming = builder(path, data=data, format='json') if data is not None else builder(path)
    if user is not None:
        force_authenticate(incoming, user=user)
    response = view.as_view()(incoming, **(kwargs or {}))
    if response.status_code >= 400:
        raise RuntimeError(f'{method} {path} returned {response.status_code}: {response.data}')
    return response


source = Product.objects.get(slug='basic-tee', is_active=True)
original_links = list(
    ProductLink.objects.filter(source=source, intent='outfit')
    .order_by('order', 'id').values_list('target_id', flat=True)
)
if len(original_links) < 2:
    raise RuntimeError('Basic Tee needs at least two outfit products for this walkthrough.')
curated_order = list(reversed(original_links))
target = Product.objects.get(pk=curated_order[0], is_active=True)
source_variant = source.variants.filter(stock__gt=0).order_by('id').first()
target_variant = target.variants.filter(stock__gt=0).order_by('id').first()
if not source_variant or not target_variant:
    raise RuntimeError('Walkthrough products require stock.')
stock_before = {source_variant.id: source_variant.stock, target_variant.id: target_variant.stock}
orders_before = Order.objects.count()
suffix = str(int(time.time() * 1000))

with transaction.atomic():
    User = get_user_model()
    owner = User.objects.create_user(username=f'phase6_owner_{suffix}', password='temporary')
    owner.is_staff = True
    owner.save(update_fields=['is_staff'])
    buyer = User.objects.create_user(username=f'phase6_buyer_{suffix}', password='temporary')

    owner_response = request(
        AdminProductLinksView, 'PUT',
        f'/api/admin/products/{source.id}/links/outfit/',
        user=owner,
        data={'product_ids': curated_order},
        kwargs={'pk': source.id, 'intent': 'outfit'},
    )
    assert owner_response.data['product_ids'] == curated_order

    related = request(
        ProductRelatedView, 'GET',
        f'/api/products/{source.slug}/related/?intent=outfit',
        kwargs={'slug': source.slug},
    )
    visible_ids = [item['id'] for item in related.data['products']]
    assert visible_ids == curated_order, (visible_ids, curated_order)

    listing = request(ProductListView, 'GET', '/api/products/?collection=t-shirts')
    assert source.slug in [item['slug'] for item in listing.data]
    detail = request(
        ProductDetailView, 'GET', f'/api/products/{source.slug}/',
        kwargs={'slug': source.slug},
    )
    assert detail.data['slug'] == source.slug

    for product, variant in ((source, source_variant), (target, target_variant)):
        request(
            CartItemAddView, 'POST', '/api/cart/items/', user=buyer,
            data={'product_slug': product.slug, 'variant_id': variant.id, 'quantity': 1},
        )
    quote = request(CartView, 'GET', '/api/cart/', user=buyer).data
    assert len(quote['items']) == 2

    order = request(
        PlaceOrderView, 'POST', '/api/orders/place/', user=buyer,
        data={
            'full_name': 'Phase 6 Buyer', 'phone': '5550100',
            'address_line1': '1 Local Test Street', 'city': 'Test City',
            'state': 'Test State', 'postal_code': '1000', 'country': 'US',
        },
    )
    assert order.status_code == 201
    for quote_key, order_key in (
        ('subtotal', 'subtotal_amount'),
        ('discount', 'discount_amount'),
        ('total', 'total_amount'),
    ):
        assert Decimal(str(quote[quote_key])) == Decimal(str(order.data[order_key]))
    assert len(order.data['items']) == 2
    assert request(CartView, 'GET', '/api/cart/', user=buyer).data['items'] == []
    for variant_id, original_stock in stock_before.items():
        assert ProductVariant.objects.get(pk=variant_id).stock == original_stock - 1

    bundle = ProductsBundleSection.objects.filter(is_active=True).prefetch_related('bundle_products').first()
    if bundle is None:
        raise RuntimeError('A configured active bundle is needed for the bundle walkthrough.')
    bundle_products = list(bundle.bundle_products.all())
    if len(bundle_products) != 2:
        raise RuntimeError('The active bundle needs exactly two products.')
    bundle_variants = [product.variants.filter(stock__gt=0).order_by('id').first() for product in bundle_products]
    if any(variant is None for variant in bundle_variants):
        raise RuntimeError('The active bundle needs in-stock variants.')
    bundle_quote = request(
        CartBundleAddView, 'POST', '/api/cart/bundles/', user=buyer,
        data={'bundle_id': bundle.id, 'variant_ids': [variant.id for variant in bundle_variants]},
    ).data
    assert bundle_quote['item_count'] == 2
    assert bundle_quote['applied_offer']['type'] == 'bundle'
    second_bundle_variant = bundle_variants[1]
    original_bundle_stock = second_bundle_variant.stock
    second_bundle_variant.stock = 1
    second_bundle_variant.save(update_fields=['stock'])
    invalid_request = factory.post('/api/cart/bundles/', {
        'bundle_id': bundle.id, 'variant_ids': [variant.id for variant in bundle_variants],
    }, format='json')
    force_authenticate(invalid_request, user=buyer)
    rejected = CartBundleAddView.as_view()(invalid_request)
    assert rejected.status_code == 400
    assert [item['quantity'] for item in request(CartView, 'GET', '/api/cart/', user=buyer).data['items']] == [1, 1]
    second_bundle_variant.stock = original_bundle_stock
    second_bundle_variant.save(update_fields=['stock'])

    result = {
        'owner_link_order_saved': curated_order,
        'buyer_outfit_order_seen': visible_ids,
        'collection_product_seen': source.slug,
        'product_detail_seen': detail.data['slug'],
        'cart_item_count': len(quote['items']),
        'quote_subtotal': str(quote['subtotal']),
        'quote_discount': str(quote['discount']),
        'quote_total': str(quote['total']),
        'stored_order_total': str(order.data['total_amount']),
        'stock_decrement_verified': True,
        'cart_cleared_verified': True,
        'atomic_bundle_added': bundle.id,
        'bundle_cart_total': str(bundle_quote['total']),
        'bundle_failure_kept_cart_unchanged': True,
        'persisted': False,
    }
    transaction.set_rollback(True)

assert Order.objects.count() == orders_before
assert list(
    ProductLink.objects.filter(source=source, intent='outfit')
    .order_by('order', 'id').values_list('target_id', flat=True)
) == original_links
for variant_id, original_stock in stock_before.items():
    assert ProductVariant.objects.get(pk=variant_id).stock == original_stock
assert not User.objects.filter(username__in=[owner.username, buyer.username]).exists()

report = Path(options.output)
report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
