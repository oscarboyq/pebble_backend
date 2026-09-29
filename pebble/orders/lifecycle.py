from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import ValidationError

from products.models import ProductVariant
from .models import Order, OrderStatusEvent


ALLOWED_TRANSITIONS = {
    'pending': {'confirmed', 'cancelled'},
    'confirmed': {'shipped', 'cancelled'},
    'shipped': {'delivered'},
    'delivered': set(),
    'cancelled': set(),
}
SHIPPING_FIELDS = (
    'carrier', 'tracking_number', 'tracking_url', 'handled_by',
    'estimated_delivery', 'shipping_notes',
)


@transaction.atomic
def update_order_status(order_id, data, actor):
    order = Order.objects.select_for_update().get(pk=order_id)
    target = data['status']
    changed = target != order.status
    if changed and target not in ALLOWED_TRANSITIONS.get(order.status, set()):
        raise ValidationError({
            'status': f'Cannot change an order from {order.status} to {target}.'
        })

    shipping_updates = {key: data[key] for key in SHIPPING_FIELDS if key in data}
    if shipping_updates and target != 'shipped':
        raise ValidationError({'status': 'Shipping details can be edited while the order is shipped.'})
    if not changed and not shipping_updates:
        raise ValidationError({'status': 'Choose a new status or update shipping details.'})

    if changed and target == 'cancelled':
        # Checkout deducts stock. Restore it once, while the order row is locked.
        quantities = {}
        for variant_id, quantity in order.items.exclude(variant_id=None).values_list('variant_id', 'quantity'):
            quantities[variant_id] = quantities.get(variant_id, 0) + quantity
        for variant in ProductVariant.objects.select_for_update().filter(pk__in=quantities).order_by('pk'):
            ProductVariant.objects.filter(pk=variant.pk).update(stock=F('stock') + quantities[variant.pk])

    order.status = target
    if target == 'shipped':
        for key, value in shipping_updates.items():
            setattr(order, key, value)
        if changed:
            from django.utils import timezone
            order.shipped_at = timezone.now()
    order.save()
    if changed:
        OrderStatusEvent.objects.create(
            order=order,
            status=target,
            changed_by=actor,
            note=data.get('status_note', ''),
        )
    return order
