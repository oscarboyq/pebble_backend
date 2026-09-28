from django.db import migrations


def forwards(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    for order in Order.objects.all().iterator():
        total = str(order.total_amount)
        lines = [
            {'product_id': item.product_id, 'variant_id': item.variant_id,
             'quantity': item.quantity, 'unit_price': str(item.unit_price),
             'line_total': str(item.line_total)}
            for item in order.items.all()
        ]
        order.subtotal_amount = order.total_amount
        order.pricing_snapshot = {
            'subtotal': total, 'discount': '0.00', 'total': total,
            'applied_offer': None, 'coupon_code': '', 'lines': lines,
        }
        order.save(update_fields=['subtotal_amount', 'pricing_snapshot'])


class Migration(migrations.Migration):
    dependencies = [('orders', '0003_order_applied_offer_name_order_applied_offer_type_and_more')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
