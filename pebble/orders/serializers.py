from rest_framework import serializers
from .models import Order, OrderItem
from products.serializers import ProductSerializer, ProductVariantSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    variant = ProductVariantSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'variant', 'quantity', 'unit_price', 'line_total']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'status',
            'full_name', 'phone',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country',
            'subtotal_amount', 'discount_amount', 'applied_offer_type',
            'applied_offer_name', 'coupon_code', 'pricing_snapshot', 'total_amount',
            # shipping dispatch fields
            'carrier', 'tracking_number', 'handled_by',
            'estimated_delivery', 'shipping_notes', 'shipped_at',
            'created_at', 'updated_at',
            'items',
        ]


class PlaceOrderSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20)
    address_line1 = serializers.CharField(max_length=255)
    address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=100, default='united states')
