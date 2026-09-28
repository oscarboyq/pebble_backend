"""Rule engine that resolves ``SmartCollection`` rules into ``Product`` querysets.

Kept free of DRF so it can be unit-tested and reused by storefront/admin views
and preview endpoints.
"""

from datetime import timedelta

from django.db.models import (
    Avg,
    Case,
    F,
    IntegerField,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from products.models import Product


# ── value coercion helpers ───────────────────────────────────────────────────

def _as_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_list(value):
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ('true', '1', 'yes', 'on')
    return bool(value)


def _within_days_value(value):
    if isinstance(value, dict):
        value = value.get('days')
    return _as_number(value)


# ── rule → Q ─────────────────────────────────────────────────────────────────

def _build_q(field, operator, value, annotations):
    """Return a ``Q`` for a rule, registering any needed ``annotations``.

    Returns ``None`` for unsupported/invalid combinations (the rule is skipped).
    """
    if field == 'created_at':
        if operator == 'within_days':
            days = _within_days_value(value)
            if days is None:
                return None
            return Q(created_at__gte=timezone.now() - timedelta(days=days))
        if operator in ('gte', 'gt'):
            return Q(created_at__gte=value)
        if operator in ('lte', 'lt'):
            return Q(created_at__lte=value)
        if operator == 'eq':
            return Q(created_at__date=value)
        return None

    if field == 'price':
        num = _as_number(value)
        if num is None:
            return None
        op_map = {
            'eq': Q(price=num),
            'neq': ~Q(price=num),
            'gt': Q(price__gt=num),
            'gte': Q(price__gte=num),
            'lt': Q(price__lt=num),
            'lte': Q(price__lte=num),
        }
        return op_map.get(operator)

    if field == 'category':
        if operator == 'in':
            slugs = _as_list(value)
            return Q(category__slug__in=slugs) if slugs else None
        if operator == 'eq':
            return Q(category__slug=value)
        if operator == 'neq':
            return ~Q(category__slug=value)
        return None

    if field == 'gender':
        if operator == 'in':
            values = _as_list(value)
            return Q(category__gender__in=values) if values else None
        if operator == 'eq':
            return Q(category__gender=value)
        if operator == 'neq':
            return ~Q(category__gender=value)
        return None

    if field == 'in_stock':
        want = _as_bool(value)
        if want:
            return Q(variants__stock__gt=0)
        annotations['_total_stock'] = Coalesce(Sum('variants__stock'), 0)
        return Q(_total_stock=0)

    if field == 'on_sale':
        want = _as_bool(value)
        if want:
            return Q(compare_at_price__isnull=False) & Q(compare_at_price__gt=F('price'))
        return Q(compare_at_price__isnull=True) | Q(compare_at_price__lte=F('price'))

    if field == 'badge':
        if operator == 'in':
            badges = _as_list(value)
            return Q(badge__in=badges) if badges else None
        if operator == 'eq':
            return Q(badge=value)
        if operator == 'neq':
            return ~Q(badge=value)
        return None

    if field == 'tag':
        if operator == 'in':
            tags = _as_list(value)
            return Q(tags__slug__in=tags) if tags else None
        if operator == 'eq':
            return Q(tags__slug=value)
        if operator == 'neq':
            return ~Q(tags__slug=value)
        return None

    if field == 'rating':
        num = _as_number(value)
        if num is None:
            return None
        annotations['_avg_rating'] = Avg('reviews__rating')
        op_map = {
            'eq': Q(_avg_rating=num),
            'gte': Q(_avg_rating__gte=num),
            'gt': Q(_avg_rating__gt=num),
            'lte': Q(_avg_rating__lte=num),
            'lt': Q(_avg_rating__lt=num),
        }
        return op_map.get(operator)

    return None


def _combine(q_objects, match_mode):
    combined = q_objects[0]
    for q in q_objects[1:]:
        combined = (combined & q) if match_mode == 'all' else (combined | q)
    return combined


def apply_rules(qs, rules, match_mode='all'):
    """Apply rule-like objects (``.field/.operator/.value``) to a queryset."""
    if not rules:
        return qs

    annotations = {}
    q_objects = []
    for rule in rules:
        q = _build_q(rule.field, rule.operator, rule.value, annotations)
        if q is not None:
            q_objects.append(q)

    if annotations:
        qs = qs.annotate(**annotations)
    if not q_objects:
        return qs

    return qs.filter(_combine(q_objects, match_mode))


# ── ordering ─────────────────────────────────────────────────────────────────

def order_by_sort(qs, sort):
    if sort == 'price_asc':
        return qs.order_by('price', 'id')
    if sort == 'price_desc':
        return qs.order_by('-price', 'id')
    if sort == 'top_rated':
        qs = qs.annotate(_sort_avg_rating=Avg('reviews__rating'))
        return qs.order_by('-_sort_avg_rating', '-created_at', '-id')
    if sort == 'best_selling':
        qs = qs.annotate(
            _total_sold=Coalesce(
                Sum(
                    'order_items__quantity',
                    filter=Q(
                        order_items__order__status__in=[
                            'confirmed',
                            'shipped',
                            'delivered',
                        ]
                    ),
                ),
                0,
            )
        )
        return qs.order_by('-_total_sold', '-created_at', '-id')
    return qs.order_by('-created_at', '-id')


def order_manually(qs, positions):
    if not positions:
        return qs
    whens = [When(id=pid, then=Value(pos)) for pid, pos in positions.items()]
    qs = qs.annotate(
        _manual_pos=Case(*whens, default=Value(1000000), output_field=IntegerField())
    )
    return qs.order_by('_manual_pos', 'id')


def apply_pins(qs, positions):
    """Boost pinned products to the front, preserving the existing ordering."""
    if not positions:
        return qs
    whens = [When(id=pid, then=Value(pos)) for pid, pos in positions.items()]
    qs = qs.annotate(
        _pin_pos=Case(*whens, default=Value(1000000), output_field=IntegerField())
    )
    existing = qs.query.order_by or ('-created_at', '-id')
    return qs.order_by('_pin_pos', *existing)


# ── collection resolution ────────────────────────────────────────────────────

def filtered_queryset(collection):
    """Products that belong to ``collection`` (rules/manual + hides), unordered."""
    qs = Product.objects.filter(is_active=True)

    if collection.collection_type == 'manual':
        product_ids = list(
            collection.manual_products.values_list('product_id', flat=True)
        )
        if not product_ids:
            return qs.none()
        qs = qs.filter(id__in=product_ids)
    else:
        qs = apply_rules(qs, list(collection.rules.all()), collection.match_mode)

    hidden_ids = list(collection.hides.values_list('product_id', flat=True))
    if hidden_ids:
        qs = qs.exclude(id__in=hidden_ids)

    qs = qs.select_related('category').prefetch_related('images', 'variants', 'reviews')
    return qs.distinct()


def resolve(collection):
    """Full resolved queryset (ordered + pinned). Callers slice ``[:limit]``."""
    qs = filtered_queryset(collection)

    if collection.collection_type == 'manual':
        positions = {
            mp.product_id: mp.position
            for mp in collection.manual_products.all()
        }
        qs = order_manually(qs, positions)
    else:
        qs = order_by_sort(qs, collection.sort)

    pin_positions = {
        pin.product_id: pin.position for pin in collection.pins.all()
    }
    return apply_pins(qs, pin_positions)


# ── preview (unsaved config) ─────────────────────────────────────────────────

class _Rule:
    __slots__ = ('field', 'operator', 'value')

    def __init__(self, data):
        self.field = data.get('field')
        self.operator = data.get('operator', 'eq')
        self.value = data.get('value')


def preview(rules_data, match_mode='all', sort='newest', limit=12,
            manual_product_ids=None, pinned_product_ids=None, hidden_product_ids=None):
    """Dry-run a set of rule dicts without persisting anything.

    Returns ``(total_matched, products[:limit])``.
    """
    qs = Product.objects.filter(is_active=True)

    if manual_product_ids:
        qs = qs.filter(id__in=manual_product_ids)
    elif rules_data:
        qs = apply_rules(qs, [_Rule(r) for r in rules_data], match_mode)

    if hidden_product_ids:
        qs = qs.exclude(id__in=hidden_product_ids)

    qs = qs.select_related('category').prefetch_related('images', 'variants', 'reviews').distinct()
    qs = order_by_sort(qs, sort)

    if pinned_product_ids:
        qs = apply_pins(
            qs, {pid: idx for idx, pid in enumerate(pinned_product_ids)}
        )

    total = qs.count()
    return total, list(qs[: max(1, int(limit or 12))])
