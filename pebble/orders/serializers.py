from rest_framework import serializers
from .models import Order, OrderItem, OrderStatusEvent
from products.serializers import ProductSerializer, ProductVariantSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    variant = ProductVariantSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'variant', 'quantity', 'unit_price', 'line_total']


class OrderStatusEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusEvent
        fields = ['id', 'status', 'occurred_at', 'note']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_events = OrderStatusEventSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'status',
            'full_name', 'phone',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country',
            'subtotal_amount', 'discount_amount', 'applied_offer_type',
            'applied_offer_name', 'coupon_code', 'pricing_snapshot', 'total_amount',
            # shipping dispatch fields
            'carrier', 'tracking_number', 'tracking_url', 'handled_by',
            'estimated_delivery', 'shipping_notes', 'shipped_at',
            'created_at', 'updated_at',
            'items', 'status_events',
        ]


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)
    carrier = serializers.ChoiceField(
        choices=Order.CARRIER_CHOICES, required=False, allow_blank=True
    )
    tracking_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    tracking_url = serializers.URLField(required=False, allow_blank=True, max_length=200)
    handled_by = serializers.CharField(max_length=150, required=False, allow_blank=True)
    estimated_delivery = serializers.DateField(required=False, allow_null=True)
    shipping_notes = serializers.CharField(required=False, allow_blank=True)
    status_note = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_tracking_url(self, value):
        if value and not value.lower().startswith('https://'):
            raise serializers.ValidationError('Use an HTTPS carrier tracking link.')
        return value


class PlaceOrderSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20)
    address_line1 = serializers.CharField(max_length=255)
    address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=100, default='united states')
