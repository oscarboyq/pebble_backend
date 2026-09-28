import hashlib
from django.core.cache import cache
from django.http import HttpResponseNotModified
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import serializers, status

from .models import (
    BannerSlide, PromoBar, MegaMenuSection, CollectionsMenuColumn,
    CollectionsMenuPromo, StoreSettings, NewInShowcaseCard, NewInShowcaseSettings, OutfitHighlightItem,
    LayeredScrollingCard, LookbookCard, LookbookHotspot, ProductsHighlightSection,
    ProductSuggestionSection, ProductsBundleSection,
    TestimonialsParallaxSection, TestimonialItem, OurStorySection, BrandPillarItem,
    FlexCarouselSection, ShopMenuPromo, PagesMenuSetting, PagesMenuCard, PagesMenuLink,
    FeaturesMenuItem, FeaturesMenuSubItem, MarqueeItem, TrustBadge,
    FooterSettings, FooterLink, FooterInstagramImage, NewsletterSubscriber, HeaderMenuItem
)
from .serializers import HomePageSerializer, FeaturedCategorySerializer
from .signals import get_homepage_cache_version, HOMEPAGE_CACHE_PREFIX, HOMEPAGE_CACHE_TTL
from products.models import Product, Category 
from products.serializers import ProductSerializer
from merchandising.models import SmartCollection
from merchandising.services import engine as collection_engine
from django.db.models import Q, Sum, Count, Prefetch
from django.db.models.functions import Coalesce


class HomePageView(APIView):
    permission_classes =[AllowAny]

    def get(self, request):
        version = get_homepage_cache_version()
        host = request.get_host()
        cache_key = f'{HOMEPAGE_CACHE_PREFIX}_{version}_{host}'
        etag = f'"{hashlib.md5(f"{version}_{host}".encode()).hexdigest()}"'

        # 1. Conditional GET check (HTTP 304 Not Modified)
        if_none_match = request.headers.get('If-None-Match')
        if if_none_match == etag:
            return HttpResponseNotModified()

        # 2. In-Memory Cache check (HTTP 200 with X-Cache: HIT)
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            response = Response(cached_data)
            response['ETag'] = etag
            response['Cache-Control'] = 'public, max-age=300, must-revalidate'
            response['X-Cache'] = 'HIT'
            return response

        banners = BannerSlide.objects.filter(is_active=True) 

        promo_bar = PromoBar.objects.filter(is_active=True).first() 

        featured_categories = Category.objects.filter(is_featured=True).annotate(
            active_count=Count('products', filter=Q(products__is_active=True))
        ).order_by('id')

        new_in_showcase = NewInShowcaseCard.objects.filter(is_active=True).order_by('order')

        outfit_highlights = OutfitHighlightItem.objects.filter(is_active=True).order_by('order')

        layered_cards = LayeredScrollingCard.objects.filter(is_active=True).order_by('order')

        lookbook_cards = LookbookCard.objects.filter(is_active=True).prefetch_related(
            Prefetch(
                'tagged_products',
                queryset=Product.objects.filter(is_active=True)
                    .select_related('category')
                    .prefetch_related('images', 'variants', 'reviews')
            ),
            Prefetch('hotspots', queryset=LookbookHotspot.objects.select_related('product__category').prefetch_related('product__images', 'product__variants', 'product__reviews').order_by('order', 'id'))
        ).order_by('order')

        products_highlight = ProductsHighlightSection.objects.filter(is_active=True).prefetch_related(
            Prefetch(
                'carousel_products',
                queryset=Product.objects.filter(is_active=True)
                    .select_related('category')
                    .prefetch_related('images', 'variants', 'reviews')
            )
        ).first()

        product_suggestion = ProductSuggestionSection.objects.filter(is_active=True).prefetch_related(
            'steps',
            Prefetch(
                'steps__products',
                queryset=Product.objects.filter(is_active=True)
                    .select_related('category')
                    .prefetch_related('images', 'variants', 'reviews')
            )
        ).first()

        products_bundle = ProductsBundleSection.objects.filter(is_active=True).prefetch_related(
            Prefetch(
                'bundle_products',
                queryset=Product.objects.filter(is_active=True)
                    .select_related('category')
                    .prefetch_related('images', 'variants', 'reviews')
            )
        ).first()

        testimonials_parallax = TestimonialsParallaxSection.objects.filter(
            is_active=True
        ).prefetch_related(
            Prefetch(
                'testimonials',
                queryset=TestimonialItem.objects.select_related('product__category').prefetch_related('product__images', 'product__variants', 'product__reviews')
            )
        ).first()

        our_story = OurStorySection.objects.filter(is_active=True).first()

        brand_pillars = BrandPillarItem.objects.filter(is_active=True).order_by('order')

        flex_carousel = FlexCarouselSection.objects.filter(is_active=True).prefetch_related('cards').first()

        best_sellers_slugs = [
            'logo-polo-red', 'stripe-sun-hat', 'backpacks-kids', 'stripe-backpack-brown',
            'sleeveless-top', 'sport-shorts-navy', 'straw-hat-beige', 'sneakers-green'
        ]
        new_arrivals_slugs = [
            'basic-tee', 'fleece-jogger-pants', 'stripe-backpack-brown', 'cuffed-shorts-khaki',
            'leather-sandals-brown', 'floral-pant-mint', 'wave-knit-top', 'sneakers-green'
        ]

        def collection_products(slug, fallback_slugs, limit=8):
            """Resolve an owner's collection, or use seed products if absent."""
            collection = SmartCollection.objects.filter(
                slug=slug, is_active=True
            ).first()
            if collection is not None:
                return list(collection_engine.resolve(collection)[:limit])

            seeded = list(
                Product.objects.filter(slug__in=fallback_slugs, is_active=True)
                .select_related('category')
                .prefetch_related('images', 'variants', 'reviews')
            )
            by_slug = {p.slug: p for p in seeded}
            result = [by_slug[s] for s in fallback_slugs if s in by_slug]
            if len(result) < limit:
                extra = (
                    Product.objects.filter(is_active=True)
                    .select_related('category')
                    .prefetch_related('images', 'variants', 'reviews')
                    .exclude(id__in=[p.id for p in result])
                    .order_by('-created_at')[: limit - len(result)]
                )
                result.extend(extra)
            return result

        best_sellers = collection_products('best-sellers', best_sellers_slugs)
        new_arrivals = collection_products('new-arrivals', new_arrivals_slugs)

        def categories_from_products(products, limit=8):
            categories = []
            seen = set()

            for product in products:
                category = product.category
                if category.id in seen:
                    continue

                seen.add(category.id)
                categories.append(category)

                if len(categories) >= limit:
                    break

            return categories

        def get_section(section_key):
            try:
                return MegaMenuSection.objects.prefetch_related(
                    'category_items__category'
                ).get(key=section_key, is_active=True)
            except MegaMenuSection.DoesNotExist:
                return None

        def manual_categories_for(section):
            if section is None or not section.use_manual_categories:
                return None

            items = list(section.category_items.all()[:8])
            return items if items else None

        section_objects = {
            key: get_section(key)
            for key in ('new_arrivals', 'best_sellers', 'clothing', 'shop_all')
        }

        def build_section(section_key, title, fallback_categories):
            section = section_objects.get(section_key)
            manual = manual_categories_for(section)

            display_mode = MegaMenuSection.DISPLAY_CATEGORIES
            products = []

            if manual is not None:
                categories = [item.category for item in manual]
            elif section is not None and section.smart_collection_id:
                display_mode = section.display_mode
                resolved = collection_engine.resolve(section.smart_collection)
                limit = section.smart_collection.limit or 12
                product_list = list(resolved[:limit])
                categories = categories_from_products(product_list)
                if display_mode == MegaMenuSection.DISPLAY_PRODUCTS:
                    products = ProductSerializer(
                        product_list,
                        many=True,
                        context={'request': request},
                    ).data
            else:
                categories = fallback_categories

            category_data = FeaturedCategorySerializer(
                categories, many=True, context={'request': request},
            ).data
            if manual is not None:
                for item, data in zip(manual, category_data):
                    if item.image_override:
                        data['image'] = request.build_absolute_uri(item.image_override.url)

            return {
                'title': title,
                'display_mode': display_mode,
                'categories': category_data,
                'products': products,
            }

        new_arrival_categories = categories_from_products(
            Product.objects.filter(is_active=True)
            .select_related('category')
            .order_by('-created_at')[:50]
        )

        best_seller_categories = categories_from_products(best_sellers)

        clothing_categories = list(
            Category.objects.filter(slug__iexact='clothing').annotate(
                active_count=Count('products', filter=Q(products__is_active=True))
            )[:8]
        )

        shop_all_categories = list(featured_categories[:8])

        shop_menu = {
            'new_arrivals': build_section(
                'new_arrivals', 'New Arrivals', new_arrival_categories
            ),
            'best_sellers': build_section(
                'best_sellers', 'Best Sellers', best_seller_categories
            ),
            'clothing': build_section(
                'clothing', 'Clothing', clothing_categories
            ),
            'shop_all': build_section(
                'shop_all', 'Shop All', shop_all_categories
            ),
        }

        shop_promos = {
            promo.section: {
                'eyebrow': promo.eyebrow,
                'title': promo.title,
                'cta_text': promo.cta_text,
                'cta_link': promo.cta_link,
                'image': request.build_absolute_uri(promo.image.url) if promo.image else None,
                'bg_color': promo.bg_color,
            }
            for promo in ShopMenuPromo.objects.filter(is_active=True)
        }

        for section_key, section_dict in shop_menu.items():
            if section_key in shop_promos:
                section_dict['promo'] = shop_promos[section_key]

        default_promo = shop_promos.get('new_arrivals') or (next(iter(shop_promos.values())) if shop_promos else None)
        if default_promo:
            shop_menu['promo'] = default_promo


        collection_columns = CollectionsMenuColumn.objects.filter(
            is_active=True
        ).prefetch_related('links')

        collection_promos = CollectionsMenuPromo.objects.filter(
            is_active=True
        )[:2]

        collections_menu = {
            'columns': [
                {
                    'id': column.id,
                    'title': column.title,
                    'order': column.order,
                    'links': [
                        {
                            'id': link.id,
                            'label': link.label,
                            'route': link.route,
                            'order': link.order,
                        }
                        for link in column.links.all() if link.is_active
                    ],
                }
                for column in collection_columns
            ],
            'promos': [
                {
                    'id': promo.id,
                    'title': promo.title,
                    'image': request.build_absolute_uri(promo.image.url)
                    if promo.image else None,
                    'route': promo.route,
                    'order': promo.order,
                }
                for promo in collection_promos
            ],
        }

        pages_setting = PagesMenuSetting.objects.first()
        pages_cards = PagesMenuCard.objects.filter(is_active=True).order_by('order')
        pages_links = PagesMenuLink.objects.filter(is_active=True).order_by('order')

        pages_menu = {
            'setting': {
                'who_we_are_title': pages_setting.who_we_are_title,
                'who_we_are_text': pages_setting.who_we_are_text,
            } if pages_setting else {
                'who_we_are_title': 'Who We Are',
                'who_we_are_text': 'We create simple, well-made essentials that balance comfort and style, giving kids the freedom to explore, play, and grow every day.',
            },
            'cards': [
                {
                    'id': card.id,
                    'title': card.title,
                    'image': request.build_absolute_uri(card.image.url) if card.image else None,
                    'route': card.route,
                    'order': card.order,
                }
                for card in pages_cards
            ],
            'links': [
                {
                    'id': link.id,
                    'label': link.label,
                    'route': link.route,
                    'order': link.order,
                }
                for link in pages_links
            ],
        }

        features_items = FeaturesMenuItem.objects.filter(is_active=True).prefetch_related('sub_items').order_by('order')
        features_menu = [
            {
                'id': item.id,
                'title': item.title,
                'route': item.route,
                'order': item.order,
                'sub_items': [
                    {
                        'id': sub.id,
                        'title': sub.title,
                        'route': sub.route,
                        'order': sub.order,
                    }
                    for sub in item.sub_items.all() if sub.is_active
                ],
            }
            for item in features_items
        ]

        store_settings = StoreSettings.objects.first()

        data = {
            'store_settings': store_settings,
            'promo_bar': promo_bar,
            'banners': banners,
            'featured_categories': featured_categories,
            'new_in_showcase': new_in_showcase,
            'new_in_showcase_settings': NewInShowcaseSettings.objects.first(),
            'outfit_highlights': outfit_highlights,
            'layered_cards': layered_cards,
            'lookbook_cards': lookbook_cards,
            'products_highlight': products_highlight,
            'product_suggestion': product_suggestion,
            'products_bundle': products_bundle,
            'testimonials_parallax': testimonials_parallax,
            'our_story': our_story,
            'brand_pillars': brand_pillars,
            'flex_carousel': flex_carousel,
            'new_arrivals': new_arrivals,
            'best_sellers': best_sellers,
            'shop_menu': shop_menu,
            'collections_menu': collections_menu,
            'pages_menu': pages_menu,
            'features_menu': features_menu,
            'marquee_items': MarqueeItem.objects.filter(is_active=True).order_by('order', 'id'),
            'header_menu': HeaderMenuItem.objects.filter(is_active=True).order_by('order', 'id'),
            'trust_badges': TrustBadge.objects.filter(is_active=True).order_by('order', 'id'),
            'footer_settings': FooterSettings.objects.filter(is_active=True).first(),
            'footer_links': FooterLink.objects.filter(is_active=True).order_by('column', 'order', 'id'),
            'footer_instagram_images': FooterInstagramImage.objects.filter(is_active=True).order_by('order', 'id'),
        }

        serializer = HomePageSerializer(data, context={'request': request})
        serialized_data = serializer.data

        # Store in cache for 10 minutes (or until model signal invalidates)
        cache.set(cache_key, serialized_data, HOMEPAGE_CACHE_TTL)

        response = Response(serialized_data)
        response['ETag'] = etag
        response['Cache-Control'] = 'public, max-age=300, must-revalidate'
        response['X-Cache'] = 'MISS'
        return response


class NewsletterInputSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class NewsletterSubscribeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = NewsletterInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].strip().lower()
        subscriber, created = NewsletterSubscriber.objects.get_or_create(
            email=email, defaults={'source': 'footer'}
        )
        if not subscriber.is_active:
            subscriber.is_active = True
            subscriber.save(update_fields=['is_active'])
        return Response({'subscribed': True}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    
