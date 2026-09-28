"""Single source of truth for cart and checkout prices.

All calculations use Decimal. The API can convert these values to JSON numbers,
while orders keep exact decimal amounts and a string-valued snapshot.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from home.models import ProductsBundleSection


CENT = Decimal('0.01')


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


class PricingError(ValueError):
    pass


@dataclass(frozen=True)
class CartQuote:
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    applied_offer: dict | None
    coupon_error: str | None
    coupon_code: str
    lines: tuple

    def snapshot(self):
        return {
            'subtotal': str(self.subtotal),
            'discount': str(self.discount),
            'total': str(self.total),
            'applied_offer': self.applied_offer,
            'coupon_code': self.coupon_code,
            'lines': [
                {'product_id': line['product_id'], 'variant_id': line['variant_id'],
                 'quantity': line['quantity'], 'unit_price': str(line['unit_price']),
                 'line_total': str(line['line_total'])}
                for line in self.lines
            ],
        }


def _coupon_discount(coupon, subtotal):
    if coupon is None:
        return Decimal('0.00'), None
    if not coupon.is_active:
        return Decimal('0.00'), 'Coupon is no longer active.'
    if coupon.expires_at and coupon.expires_at <= timezone.now():
        return Decimal('0.00'), 'Coupon has expired.'
    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        return Decimal('0.00'), 'Coupon usage limit has been reached.'
    if coupon.min_order_amount is not None and subtotal < coupon.min_order_amount:
        return Decimal('0.00'), f'Coupon requires a subtotal of at least {money(coupon.min_order_amount)}.'
    value = Decimal(coupon.discount_value)
    if value <= 0 or (coupon.discount_type == 'percent' and value > 100):
        return Decimal('0.00'), 'Coupon discount is not configured correctly.'
    if coupon.discount_type == 'percent':
        discount = money(subtotal * value / Decimal('100'))
    elif coupon.discount_type == 'fixed':
        discount = money(min(value, subtotal))
    else:
        return Decimal('0.00'), 'Coupon discount is not configured correctly.'
    return discount, None


def _bundle_offer(lines):
    best_discount = Decimal('0.00')
    best_offer = None
    for bundle in ProductsBundleSection.objects.filter(is_active=True).prefetch_related('bundle_products').order_by('id'):
        product_ids = list(bundle.bundle_products.values_list('id', flat=True))
        if len(product_ids) != 2 or not 1 <= bundle.discount_percentage <= 100:
            continue
        units = {product_id: [] for product_id in product_ids}
        for line in lines:
            if line['product_id'] in units:
                units[line['product_id']].extend([line['unit_price']] * line['quantity'])
        pairs = min(len(units[product_ids[0]]), len(units[product_ids[1]]))
        if not pairs:
            continue
        paired_subtotal = sum(
            (sum(sorted(prices, reverse=True)[:pairs], Decimal('0.00')) for prices in units.values()),
            Decimal('0.00'),
        )
        discount = money(paired_subtotal * Decimal(bundle.discount_percentage) / Decimal('100'))
        if discount > best_discount:
            best_discount = discount
            best_offer = {'type': 'bundle', 'name': bundle.heading, 'bundle_id': bundle.id, 'pairs': pairs}
    return best_discount, best_offer


def quote_cart(cart, *, items=None, coupon=None, strict_coupon=False):
    if items is None:
        items = list(cart.items.select_related('product', 'variant').order_by('id'))
    if coupon is None and cart.coupon_id:
        coupon = cart.coupon
    lines = []
    for item in items:
        unit_price = money(item.variant.price_override if item.variant and item.variant.price_override is not None else item.product.price)
        if unit_price < 0:
            raise PricingError('A product has an invalid price.')
        lines.append({
            'product_id': item.product_id, 'variant_id': item.variant_id,
            'quantity': item.quantity, 'unit_price': unit_price,
            'line_total': money(unit_price * item.quantity),
        })
    subtotal = money(sum((line['line_total'] for line in lines), Decimal('0.00')))
    bundle_discount, bundle_offer = _bundle_offer(lines)
    coupon_discount, coupon_error = _coupon_discount(coupon, subtotal)
    if strict_coupon and coupon_error:
        raise PricingError(coupon_error)
    if coupon_discount > bundle_discount:
        discount = coupon_discount
        offer = {'type': 'coupon', 'name': f'Coupon {coupon.code}', 'code': coupon.code}
    else:
        discount = bundle_discount
        offer = bundle_offer
    total = money(max(Decimal('0.00'), subtotal - discount))
    return CartQuote(
        subtotal=subtotal, discount=discount, total=total,
        applied_offer=offer, coupon_error=coupon_error,
        coupon_code=coupon.code if coupon else '', lines=tuple(lines),
    )
