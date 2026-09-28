from rest_framework import serializers
from .models import Cart, CartItem 
from products.serializers import ProductSerializer, ProductVariantSerializer 
from .pricing import quote_cart

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True) 
    variant = ProductVariantSerializer(read_only=True) 
    unit_price = serializers.FloatField(read_only=True) 
    line_total = serializers.FloatField(read_only=True) 

    class Meta:
        model = CartItem 
        fields =['id', 'product', 'variant', 'quantity', 'unit_price', 'line_total', 'added_at'] 


class CartSerializer(serializers.ModelSerializer): 
    items = CartItemSerializer(many=True, read_only=True) 
    total = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    discount = serializers.SerializerMethodField()
    applied_offer = serializers.SerializerMethodField()
    coupon_code = serializers.SerializerMethodField()
    coupon_error = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField() 

    class Meta:
        model = Cart
        fields = ['id', 'items', 'subtotal', 'discount', 'applied_offer', 'coupon_code', 'coupon_error', 'total', 'item_count', 'updated_at']

    def _quote(self, obj):
        if not hasattr(self, '_cached_quote'):
            self._cached_quote = quote_cart(obj)
        return self._cached_quote

    def get_total(self, obj):
        return float(self._quote(obj).total)

    def get_subtotal(self, obj):
        return float(self._quote(obj).subtotal)

    def get_discount(self, obj):
        return float(self._quote(obj).discount)

    def get_applied_offer(self, obj):
        return self._quote(obj).applied_offer

    def get_coupon_code(self, obj):
        return self._quote(obj).coupon_code

    def get_coupon_error(self, obj):
        return self._quote(obj).coupon_error

    def get_item_count(self, obj):
        items = obj.items.all()
        return sum(item.quantity for item in items)
    

class AddToCartSerializer(serializers.Serializer):
    product_slug = serializers.SlugField()
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, default=1)

class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


class AddBundleSerializer(serializers.Serializer):
    bundle_id = serializers.IntegerField(min_value=1)
    variant_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), min_length=2, max_length=2,
    )
