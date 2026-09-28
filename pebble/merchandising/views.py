from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from products.serializers import ProductSerializer

from .models import SmartCollection
from .services import engine


class CollectionListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        collections = SmartCollection.objects.filter(is_active=True)
        if request.query_params.get('featured', '').lower() in ('true', '1'):
            collections = collections.filter(is_featured=True)

        data = []
        for collection in collections:
            image_url = None
            if collection.image:
                image_url = request.build_absolute_uri(collection.image.url)
            data.append({
                'id': collection.id,
                'name': collection.name,
                'slug': collection.slug,
                'description': collection.description,
                'image': image_url,
                'is_featured': collection.is_featured,
                'position': collection.position,
                'collection_type': collection.collection_type,
                'sort': collection.sort,
                'limit': collection.limit,
                'product_count': engine.filtered_queryset(collection).count(),
            })
        return Response(data)


class CollectionDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        collection = get_object_or_404(
            SmartCollection, slug=slug, is_active=True
        )
        queryset = engine.resolve(collection)
        total = queryset.count()
        products = queryset[: collection.limit]

        return Response({
            'id': collection.id,
            'name': collection.name,
            'slug': collection.slug,
            'description': collection.description,
            'image': request.build_absolute_uri(collection.image.url)
            if collection.image else None,
            'is_featured': collection.is_featured,
            'collection_type': collection.collection_type,
            'sort': collection.sort,
            'limit': collection.limit,
            'product_count': total,
            'products': ProductSerializer(
                products, many=True, context={'request': request}
            ).data,
        })
