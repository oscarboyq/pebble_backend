from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from products.models import Product, ProductVariant
from coupons.models import Coupon
from cart.pricing import quote_cart, PricingError

from .models import Order, OrderItem
from cart.models import Cart
from .serializers import OrderSerializer, OrderItemSerializer, PlaceOrderSerializer


class PlaceOrderView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = PlaceOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        cart = Cart.objects.select_for_update().filter(user=request.user).first()
        if cart is None:
            return Response({'detail': 'Cart is empty.'}, status=400)
        items = list(cart.items.select_related('product', 'variant').select_for_update(of=('self',)).order_by('id'))
        if not items:
            return Response({'detail': 'Cart is empty.'}, status=400)

        # Lock catalog rows before pricing and stock checks. This prevents two
        # PostgreSQL checkouts from selling the same final units.
        products = Product.objects.select_for_update().order_by('id').in_bulk(sorted({item.product_id for item in items}))
        variant_ids = sorted({item.variant_id for item in items if item.variant_id})
        variants = ProductVariant.objects.select_for_update().order_by('id').in_bulk(variant_ids)
        quantities = {}
        for item in items:
            product = products.get(item.product_id)
            variant = variants.get(item.variant_id)
            if product is None or not product.is_active:
                return Response({'detail': f'{item.product.name} is no longer available.'}, status=400)
            if item.quantity < 1 or variant is None or variant.product_id != product.id:
                return Response({'detail': f'Select an available variant for {product.name}.'}, status=400)
            item.product = product
            item.variant = variant
            quantities[variant.id] = quantities.get(variant.id, 0) + item.quantity
        for variant_id, quantity in quantities.items():
            variant = variants[variant_id]
            if quantity > variant.stock:
                return Response({'detail': f'Only {variant.stock} units of {variant.product.name} ({variant.size or variant.color}) are available.'}, status=400)

        coupon = Coupon.objects.select_for_update().filter(pk=cart.coupon_id).first() if cart.coupon_id else None
        try:
            quote = quote_cart(cart, items=items, coupon=coupon, strict_coupon=True)
        except PricingError as exc:
            return Response({'detail': str(exc)}, status=400)

        data = serializer.validated_data
        order = Order.objects.create(
            user=request.user,
            full_name=data['full_name'],
            phone=data['phone'],
            address_line1=data['address_line1'],
            address_line2=data.get('address_line2', ''),
            city=data['city'],
            state=data['state'],
            postal_code=data['postal_code'],
            country=data.get('country', 'united states'),
            subtotal_amount=quote.subtotal,
            discount_amount=quote.discount,
            total_amount=quote.total,
            applied_offer_type=quote.applied_offer['type'] if quote.applied_offer else '',
            applied_offer_name=quote.applied_offer['name'] if quote.applied_offer else '',
            coupon_code=quote.coupon_code,
            pricing_snapshot=quote.snapshot(),
        )
        for cart_item, line in zip(items, quote.lines):
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                variant=cart_item.variant,
                quantity=cart_item.quantity,
                unit_price=line['unit_price'],
                line_total=line['line_total'],
            )
        for variant_id, quantity in quantities.items():
            variant = variants[variant_id]
            variant.stock -= quantity
            variant.save(update_fields=['stock'])
        if coupon and quote.applied_offer and quote.applied_offer['type'] == 'coupon':
            coupon.usage_count += 1
            coupon.save(update_fields=['usage_count'])
        cart.items.all().delete()
        cart.coupon = None
        cart.save(update_fields=['coupon', 'updated_at'])
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
    


class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user).prefetch_related('items__product', 'items__variant')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = Order.objects.prefetch_related('items__product', 'items__variant').get(
                id=order_id, user=request.user
            )
        except Order.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(OrderSerializer(order).data)
    
