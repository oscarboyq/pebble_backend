from django.db.models import Q
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from content.models import Page, Article
from content.serializers import PageSerializer, ArticleListSerializer, ArticleDetailSerializer
from merchandising.models import SmartCollection
from products.models import Product
from products.serializers import ProductSerializer


class PageListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        pages = Page.objects.filter(is_published=True)
        return Response(PageSerializer(pages, many=True, context={'request': request}).data)


class PageDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        page = Page.objects.filter(slug=slug, is_published=True).first()
        if page is None:
            return Response({'detail': 'Page not found.'}, status=404)
        return Response(PageSerializer(page, context={'request': request}).data)


class ArticleListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, blog_handle='news'):
        articles = Article.objects.filter(
            blog_handle=blog_handle, is_published=True
        )
        return Response(
            ArticleListSerializer(articles, many=True, context={'request': request}).data
        )


class ArticleDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, blog_handle, slug):
        article = Article.objects.filter(
            blog_handle=blog_handle, slug=slug, is_published=True
        ).first()
        if article is None:
            return Response({'detail': 'Article not found.'}, status=404)
        return Response(
            ArticleDetailSerializer(article, context={'request': request}).data
        )


class SearchView(APIView):
    """Site-wide search across products, collections, pages and articles.

    Mirrors Shopify's predictive/search resource groups so the storefront can
    render a unified search results page.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if not q:
            return Response({
                'query': q,
                'products': [],
                'collections': [],
                'pages': [],
                'articles': [],
            })

        products = (
            Product.objects.filter(is_active=True)
            .filter(
                Q(name__icontains=q)
                | Q(description__icontains=q)
                | Q(tags__name__icontains=q)
            )
            .select_related('category')
            .prefetch_related('images', 'variants', 'reviews', 'tags')
            .distinct()
            .order_by('name')[:12]
        )

        collections = SmartCollection.objects.filter(
            is_active=True, name__icontains=q
        ).order_by('name')[:6]

        pages = Page.objects.filter(
            is_published=True, title__icontains=q
        ).order_by('title')[:6]

        articles = Article.objects.filter(is_published=True).filter(
            Q(title__icontains=q) | Q(excerpt__icontains=q)
        ).order_by('-published_at')[:6]

        return Response({
            'query': q,
            'products': ProductSerializer(
                products, many=True, context={'request': request}
            ).data,
            'collections': [
                {
                    'id': c.id,
                    'name': c.name,
                    'slug': c.slug,
                    'image': request.build_absolute_uri(c.image.url)
                    if c.image else None,
                }
                for c in collections
            ],
            'pages': PageSerializer(
                pages, many=True, context={'request': request}
            ).data,
            'articles': ArticleListSerializer(
                articles, many=True, context={'request': request}
            ).data,
        })
