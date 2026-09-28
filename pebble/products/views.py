from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly, IsAuthenticated
from .models import Product, Category, Review, ProductVariant, SizeChart, ProductLink
from .serializers import (ProductSerializer, 
                          CategorySerializer, 
                          ReviewSerializer, 
                          WriteReviewSerializer,
                          SizeChartSerializer,
                          )

from django.db.models import Q, Avg, Sum, Count, Min, Max
from django.db.models.functions import Coalesce

from merchandising.models import SmartCollection
from merchandising.services import engine


# Canonical sort options exposed to clients / facet metadata.
SORT_OPTIONS = [
    {'value': 'newest', 'label': 'Featured'},
    {'value': 'best_selling', 'label': 'Best selling'},
    {'value': 'price_asc', 'label': 'Price, low to high'},
    {'value': 'price_desc', 'label': 'Price, high to low'},
    {'value': 'top_rated', 'label': 'Highest rated'},
    {'value': 'manual', 'label': 'Manual'},
]

# Backwards-compatible category slug aliasing used by the storefront menus.
CATEGORY_ALIASES = {
    'accessories': ['girls-accessories'],
    'dresses': ['girls-dresses'],
    'shoes': ['girls-shoes', 'sandals'],
    'bags': ['girls-bags'],
    'skirts': ['girls-skirts'],
    'sweaters': ['girls-sweaters', 'knitwear'],
    'outerwear': ['girls-outerwear', 'coats-jackets'],
    'knitwear': ['sweaters', 'girls-sweaters'],
    'jeans': ['pants'],
    'legging': ['pants'],
}


def _with_relations(qs):
    return qs.select_related('category').prefetch_related(
        'images', 'variants', 'reviews', 'tags',
    )


def filter_products(request):
    """Apply every storefront product filter.

    Returns ``(queryset, collection, error_response)`` where ``error_response``
    is a DRF ``Response`` when a requested collection does not exist.
    """
    products = Product.objects.filter(is_active=True)
    collection = None

    collection_slug = request.query_params.get('collection', '').strip()
    if collection_slug:
        collection = SmartCollection.objects.filter(
            slug=collection_slug, is_active=True
        ).first()
        if collection is None:
            return None, None, Response(
                {'detail': 'Collection not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        products = engine.filtered_queryset(collection)

    search = request.query_params.get('search', '').strip()
    category = request.query_params.get('category', '').strip()
    product_type = request.query_params.get('product_type', '').strip()
    gender = request.query_params.get('gender', '').strip()
    min_price = request.query_params.get('min_price', '').strip()
    max_price = request.query_params.get('max_price', '').strip()
    color = request.query_params.get('color', '').strip()
    size = request.query_params.get('size', '').strip()
    tag = request.query_params.get('tag', '').strip()
    rating = request.query_params.get('rating', '').strip()
    sale = request.query_params.get('sale', '').strip().lower()
    availability = request.query_params.get('availability', '').strip().lower()
    in_stock_param = request.query_params.get('in_stock', '').strip().lower()

    if search:
        products = products.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    if category:
        category_slugs = [category] + CATEGORY_ALIASES.get(category, [])
        products = products.filter(category__slug__in=category_slugs).distinct()

    if product_type:
        products = products.filter(product_type__iexact=product_type)

    if gender:
        products = products.filter(category__gender__iexact=gender).distinct()

    if sale in ('true', '1'):
        products = products.filter(
            compare_at_price__isnull=False, compare_at_price__gt=0
        ).exclude(compare_at_price=None)

    if availability == 'in_stock' or in_stock_param in ('true', '1'):
        products = products.filter(variants__stock__gt=0).distinct()
    elif availability == 'out_of_stock' or in_stock_param in ('false', '0'):
        products = products.annotate(
            _total_stock=Coalesce(Sum('variants__stock'), 0)
        ).filter(_total_stock=0)

    if min_price:
        products = products.filter(price__gte=min_price)

    if max_price:
        products = products.filter(price__lte=max_price)

    if color:
        products = products.filter(variants__color__iexact=color).distinct()

    if size:
        products = products.filter(variants__size__iexact=size).distinct()

    if tag:
        tag_slugs = [t.strip() for t in tag.split(',') if t.strip()]
        if tag_slugs:
            products = products.filter(tags__slug__in=tag_slugs).distinct()

    if rating:
        try:
            min_rating = float(rating)
        except (TypeError, ValueError):
            min_rating = None
        if min_rating is not None:
            products = products.annotate(
                _filter_avg_rating=Avg('reviews__rating')
            ).filter(_filter_avg_rating__gte=min_rating)

    return _with_relations(products), collection, None


def sort_products(products, collection, sort):
    effective_sort = sort or (collection.sort if collection is not None else 'newest')

    if effective_sort == 'price_asc':
        return products.order_by('price', 'id')
    if effective_sort == 'price_desc':
        return products.order_by('-price', 'id')
    if effective_sort == 'top_rated':
        return products.annotate(
            avg_rating=Avg('reviews__rating')
        ).order_by('-avg_rating', '-created_at', '-id')
    if effective_sort == 'best_selling':
        return products.annotate(
            total_sold=Coalesce(
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
        ).order_by('-total_sold', '-created_at', '-id')
    if effective_sort == 'manual' and collection is not None:
        positions = {
            mp.product_id: mp.position
            for mp in collection.manual_products.all()
        }
        return engine.order_manually(products, positions)
    return products.order_by('-created_at', '-id')


class ProductListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        products, collection, error = filter_products(request)
        if error is not None:
            return error

        sort = request.query_params.get('sort', '').strip()
        products = sort_products(products, collection, sort)

        if collection is not None:
            pin_positions = {
                pin.product_id: pin.position for pin in collection.pins.all()
            }
            products = engine.apply_pins(products, pin_positions)

        total = products.count()

        # Opt-in pagination keeps the default (plain list) response backwards
        # compatible with existing clients such as the Flutter storefront.
        page_raw = request.query_params.get('page')
        size_raw = request.query_params.get('page_size') or request.query_params.get('limit')
        if page_raw or size_raw:
            try:
                page = max(1, int(page_raw or 1))
            except (TypeError, ValueError):
                page = 1
            try:
                page_size = min(100, max(1, int(size_raw or 24)))
            except (TypeError, ValueError):
                page_size = 24
            start = (page - 1) * page_size
            page_items = list(products[start:start + page_size])
            serializer = ProductSerializer(
                page_items, many=True, context={'request': request}
            )
            response = Response({
                'count': total,
                'page': page,
                'page_size': page_size,
                'results': serializer.data,
            })
            response['X-Total-Count'] = str(total)
            return response

        serializer = ProductSerializer(products, many=True, context={'request': request})
        response = Response(serializer.data)
        response['X-Total-Count'] = str(total)
        return response


class ProductFacetsView(APIView):
    """Filter metadata (buckets + counts) for the product/collection listing."""

    permission_classes = [AllowAny]

    def get(self, request):
        products, collection, error = filter_products(request)
        if error is not None:
            return error

        total = products.count()

        in_stock = products.filter(variants__stock__gt=0).distinct().count()

        price = products.aggregate(lo=Min('price'), hi=Max('price'))

        color_rows = (
            ProductVariant.objects
            .filter(product__in=products, color__gt='')
            .values('color')
            .annotate(count=Count('product', distinct=True))
            .order_by('-count', 'color')
        )
        size_rows = (
            ProductVariant.objects
            .filter(product__in=products, size__gt='')
            .values('size')
            .annotate(count=Count('product', distinct=True))
            .order_by('-count', 'size')
        )
        category_rows = (
            products
            .values('category__slug', 'category__name')
            .annotate(count=Count('id', distinct=True))
            .order_by('-count')
        )
        type_rows = (
            products.exclude(product_type='')
            .values('product_type')
            .annotate(count=Count('id', distinct=True))
            .order_by('product_type')
        )
        tag_rows = (
            products
            .filter(tags__isnull=False)
            .values('tags__slug', 'tags__name')
            .annotate(count=Count('id', distinct=True))
            .order_by('-count')
        )

        return Response({
            'total': total,
            'collection': collection.slug if collection is not None else None,
            'availability': [
                {'value': 'in_stock', 'label': 'In stock', 'count': in_stock},
                {'value': 'out_of_stock', 'label': 'Out of stock', 'count': max(0, total - in_stock)},
            ],
            'price': {
                'min': float(price['lo']) if price['lo'] is not None else None,
                'max': float(price['hi']) if price['hi'] is not None else None,
            },
            'colors': [
                {'value': r['color'], 'label': r['color'], 'count': r['count']}
                for r in color_rows
            ],
            'sizes': [
                {'value': r['size'], 'label': r['size'], 'count': r['count']}
                for r in size_rows
            ],
            'categories': [
                {
                    'value': r['category__slug'],
                    'label': r['category__name'],
                    'count': r['count'],
                }
                for r in category_rows
            ],
            'product_types': [
                {
                    'value': r['product_type'],
                    'label': r['product_type'],
                    'count': r['count'],
                }
                for r in type_rows
            ],
            'tags': [
                {
                    'value': r['tags__slug'],
                    'label': r['tags__name'],
                    'count': r['count'],
                }
                for r in tag_rows
            ],
            'sort_options': SORT_OPTIONS,
        })


class ProductRelatedView(APIView):
    """Related / complementary products for a product.

    Mirrors Shopify's ``/recommendations/products`` shape:
    ``{"intent": "...", "products": [...]}``.
    """

    permission_classes = [AllowAny]

    def get(self, request, slug):
        try:
            product = Product.objects.select_related('category').get(
                slug=slug, is_active=True
            )
        except Product.DoesNotExist:
            return Response(
                {'detail': 'Product not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        intent = request.query_params.get('intent', 'related').strip().lower()
        if intent not in ('related', 'complementary', 'outfit'):
            intent = 'related'
        try:
            limit = min(24, max(1, int(request.query_params.get('limit', 8))))
        except (TypeError, ValueError):
            limit = 8

        curated_ids = list(ProductLink.objects.filter(
            source=product, intent=intent, target__is_active=True
        ).order_by('order', 'id').values_list('target_id', flat=True)[:limit])
        curated = list(_with_relations(Product.objects.filter(id__in=curated_ids, is_active=True)))
        by_id = {item.id: item for item in curated}
        related = [by_id[pk] for pk in curated_ids if pk in by_id]
        # Only ordinary related recommendations use an inferred fallback.
        if intent == 'related' and len(related) < limit:
            seen = {item.id for item in related}
            related.extend(item for item in self._related(product, limit) if item.id not in seen)
        related = related[:limit]

        serializer = ProductSerializer(related, many=True, context={'request': request})
        return Response({'intent': intent, 'products': serializer.data})

    def _related(self, product, limit):
        base = _with_relations(
            Product.objects.filter(is_active=True).exclude(id=product.id)
        )
        result = []
        seen = set()

        def add(items):
            for item in items:
                if item.id not in seen:
                    seen.add(item.id)
                    result.append(item)

        # 1. Same category (strongest signal)
        add(base.filter(category=product.category).order_by('-created_at')[: limit * 3])

        # 2. Shared tags
        tag_ids = list(product.tags.values_list('id', flat=True))
        if tag_ids and len(result) < limit:
            add(
                base.filter(tags__in=tag_ids)
                .distinct()
                .order_by('-created_at')[: limit * 3]
            )

        # 3. Fallback: newest active products
        if len(result) < limit:
            add(base.order_by('-created_at')[: limit * 2])

        return result[:limit]



class ProductDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        try:
            product = Product.objects.prefetch_related(
                'images', 'variants', 'reviews'
            ).select_related('category').get(slug=slug, is_active=True)
        except Product.DoesNotExist:
            return Response(
                {'detail': 'Product not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ProductSerializer(product, context={'request': request})
        return Response(serializer.data)


class CategoryListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        category = Category.objects.annotate(
            active_count=Count('products', filter=Q(products__is_active=True))
        ).order_by('name') 
        serializer = CategorySerializer(category, many=True)
        return Response(serializer.data)



class ProductReviewListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, slug):
        try:
            product = Product.objects.get(slug=slug, is_active=True)
        except Product.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        # Public readers only see approved reviews. The owner may see their own
        # pending review so they can confirm it was submitted.
        reviews = product.reviews.select_related('user').filter(is_approved=True)
        if request.user.is_authenticated:
            mine = product.reviews.filter(user=request.user)
            reviews = (reviews | mine).distinct()
        return Response(ReviewSerializer(reviews, many=True).data)

    def post(self, request, slug):
        try:
            product = Product.objects.get(slug=slug, is_active=True)
        except Product.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = WriteReviewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        review, created = Review.objects.update_or_create(
            product=product,
            user=request.user,
            defaults=serializer.validated_data,
        )
        return Response(
            ReviewSerializer(review).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
    

class ProductReviewDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, slug):
        try:
            review = Review.objects.get(product__slug=slug, user=request.user)
            review.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Review.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        


class ProductSuggestionsView(APIView): 
    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if len(q) < 2:
            return Response([])
        
        products = (
            Product.objects
            .filter(is_active=True, name__icontains=q)
            .values('name', 'slug')
            .order_by('name')[:8]
        )
        return Response(list(products))


class SizeChartView(APIView):
    """Public size chart for the product detail page."""

    permission_classes = [AllowAny]

    def get(self, request):
        chart = SizeChart.objects.filter(is_active=True).first()
        if chart is None:
            return Response(None)
        return Response(
            SizeChartSerializer(chart, context={'request': request}).data
        )
