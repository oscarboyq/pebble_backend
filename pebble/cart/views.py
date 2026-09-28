from rest_framework.views import APIView 
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Cart, CartItem
from .serializers import CartSerializer, AddToCartSerializer, UpdateCartItemSerializer, AddBundleSerializer
from products.models import Product, ProductVariant 
from coupons.models import Coupon
from django.db import transaction
from .pricing import quote_cart, PricingError
from home.models import ProductsBundleSection




def get_or_create_cart(user):
    """Get the user's cart, creating it if it doesn't exist yet."""
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart

class CartView(APIView):
    """GET — return the current user's full cart."""
    def get(self, request):
        cart = get_or_create_cart(request.user) 
        cart = Cart.objects.prefetch_related('items__product', 'items__variant').get(pk=cart.pk)
        serializer = CartSerializer(cart) 
        return Response(serializer.data) 
    

class CartItemAddView(APIView):
    """POST — add a product to the cart (or increase quantity if already there)."""
    @transaction.atomic
    def post(self, request): 
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = get_object_or_404(Product, slug=serializer.validated_data['product_slug'], is_active=True)
        variant_id = serializer.validated_data.get('variant_id') 
        if not variant_id:
            return Response({'detail': 'Select an available product variant before adding to cart.'}, status=400)
        cart = get_or_create_cart(request.user)
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        variant = get_object_or_404(ProductVariant.objects.select_for_update(), id=variant_id, product=product)
        
        quantity = serializer.validated_data['quantity'] 
        current = CartItem.objects.filter(cart=cart, product=product, variant=variant).first()
        desired = quantity + (current.quantity if current else 0)
        if desired > variant.stock:
            return Response({'detail': f'Only {variant.stock} units of this variant are available.'}, status=400)

        # unique_together handles the lookup — get existing or create new

        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, variant=variant,
            defaults={'quantity': quantity}
        )
        if not created:
            # Item already in cart — add to existing quantity
            item.quantity += quantity
            item.save()
        
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


class CartBundleAddView(APIView):
    """Add both configured bundle variants in one stock-validated transaction."""

    @transaction.atomic
    def post(self, request):
        serializer = AddBundleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bundle = ProductsBundleSection.objects.filter(
            pk=serializer.validated_data['bundle_id'], is_active=True,
        ).first()
        if bundle is None:
            return Response({'detail': 'This bundle is unavailable.'}, status=400)
        expected_products = set(bundle.bundle_products.values_list('id', flat=True))
        if len(expected_products) != 2:
            return Response({'detail': 'This bundle is not configured for two products.'}, status=400)
        variant_ids = serializer.validated_data['variant_ids']
        if len(set(variant_ids)) != 2:
            return Response({'detail': 'Select one variant for each bundle product.'}, status=400)
        cart = get_or_create_cart(request.user)
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        variants = list(
            ProductVariant.objects.select_for_update().select_related('product')
            .filter(pk__in=variant_ids).order_by('pk')
        )
        if (len(variants) != 2 or
                {variant.product_id for variant in variants} != expected_products or
                any(not variant.product.is_active for variant in variants)):
            return Response({'detail': 'Select available variants from both bundle products.'}, status=400)
        existing = {
            item.variant_id: item for item in CartItem.objects.filter(cart=cart, variant_id__in=variant_ids)
        }
        for variant in variants:
            desired = (existing[variant.id].quantity if variant.id in existing else 0) + 1
            if desired > variant.stock:
                return Response({'detail': f'Only {variant.stock} units of {variant.product.name} are available.'}, status=400)
        for variant in variants:
            item = existing.get(variant.id)
            if item:
                item.quantity += 1
                item.save(update_fields=['quantity'])
            else:
                CartItem.objects.create(cart=cart, product=variant.product, variant=variant, quantity=1)
        return Response(CartSerializer(cart).data)
    

class CartItemUpdateView(APIView):
    """PATCH — set a specific quantity. DELETE — remove the item."""
    @transaction.atomic
    def patch(self, request, item_id):
        cart = get_or_create_cart(request.user)
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)

        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not item.variant_id:
            return Response({'detail': 'This item has no purchasable variant.'}, status=400)
        variant = ProductVariant.objects.select_for_update().get(pk=item.variant_id)
        if serializer.validated_data['quantity'] > variant.stock:
            return Response({'detail': f'Only {variant.stock} units of this variant are available.'}, status=400)

        item.quantity = serializer.validated_data['quantity']
        item.save()

        return Response(CartSerializer(cart).data)
    
    @transaction.atomic
    def delete(self, request, item_id):
        cart = get_or_create_cart(request.user)
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        item.delete()
        return Response(CartSerializer(cart).data) 
    
class CartClearView(APIView):
    """DELETE — remove all items from the cart."""
    @transaction.atomic
    def delete(self, request):
        cart = get_or_create_cart(request.user)
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        cart.items.all().delete() 
        cart.coupon = None
        cart.save(update_fields=['coupon', 'updated_at'])
        return Response(CartSerializer(cart).data)


class CartCouponView(APIView):
    """Attach or remove a coupon; checkout revalidates it under a row lock."""

    @transaction.atomic
    def post(self, request):
        code = str(request.data.get('code') or '').strip()
        if not code:
            return Response({'detail': 'Enter a coupon code.'}, status=400)
        coupon = Coupon.objects.filter(code__iexact=code).first()
        if coupon is None:
            return Response({'detail': 'Coupon code was not found.'}, status=400)
        cart = get_or_create_cart(request.user)
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        try:
            quote_cart(cart, coupon=coupon, strict_coupon=True)
        except PricingError as exc:
            return Response({'detail': str(exc)}, status=400)
        cart.coupon = coupon
        cart.save(update_fields=['coupon', 'updated_at'])
        return Response(CartSerializer(cart).data)

    @transaction.atomic
    def delete(self, request):
        cart = get_or_create_cart(request.user)
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        cart.coupon = None
        cart.save(update_fields=['coupon', 'updated_at'])
        return Response(CartSerializer(cart).data)
