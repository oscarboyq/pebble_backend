from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from products.models import Product
from .models import WishlistItem
from .serializers import WishlistItemSerializer


class WishlistView(APIView):
    permission_claases = [IsAuthenticated]

    def get(self, request):
        items = WishlistItem.objects.filter(user=request.user).select_related('product')
        return Response(WishlistItemSerializer(items, many=True).data) 
    

class WishlistToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        try:
            product = Product.objects.get(slug= slug, is_active=True)
        except Product.DoesNotExist:
            return Response({'detail': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        item, created = WishlistItem.objects.get_or_create(user=request.user, product=product)
        if not created:
            item.delete()
            return Response({'wishlisted': False})
        return Response({'wishlisted': True}, status=status.HTTP_201_CREATED)
    

class WishlistSlugsView(APIView):
    """Returns only the slugs of wishlisted products — lightweight for badge checks."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        slugs = WishlistItem.objects.filter(user=request.user).values_list(
            'product__slug', flat=True
        )
        return Response(list(slugs))
