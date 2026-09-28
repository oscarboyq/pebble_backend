import hashlib
import time
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete, m2m_changed

from .models import (
    BannerSlide, PromoBar, StoreSettings, MegaMenuSection, MegaMenuSectionCategory,
    CollectionsMenuColumn, CollectionsMenuLink, CollectionsMenuPromo,
    NewInShowcaseCard, NewInShowcaseSettings, OutfitHighlightItem, LayeredScrollingCard, LookbookCard,
    ProductsHighlightSection, ProductSuggestionSection, ProductSuggestionStep,
    ProductsBundleSection, TestimonialsParallaxSection, TestimonialItem,
    OurStorySection, BrandPillarItem, FlexCarouselSection, FlexCarouselCard,
    ShopMenuPromo, PagesMenuSetting, PagesMenuCard, PagesMenuLink,
    FeaturesMenuItem, FeaturesMenuSubItem, LookbookHotspot, MarqueeItem,
    TrustBadge, FooterSettings, FooterLink, FooterInstagramImage, HeaderMenuItem
)
from products.models import Product, Category, ProductImage, ProductVariant, Tag
from merchandising.models import (
    SmartCollection, SmartCollectionRule, SmartCollectionPin,
    SmartCollectionHide, SmartCollectionManualProduct,
)

HOMEPAGE_CACHE_VERSION_KEY = 'pebble_homepage_cache_version'
HOMEPAGE_CACHE_PREFIX = 'pebble_homepage_data'
HOMEPAGE_CACHE_TTL = 600  # 10 minutes


def get_homepage_cache_version() -> int:
    version = cache.get(HOMEPAGE_CACHE_VERSION_KEY)
    if version is None:
        version = time.time_ns()
        cache.set(HOMEPAGE_CACHE_VERSION_KEY, version, None)
    return version


def invalidate_homepage_cache(*args, **kwargs):
    """
    Invalidates the homepage cache by incrementing the cache version.
    This guarantees that all subsequent requests instantly bypass stale cached data.
    """
    try:
        cache.incr(HOMEPAGE_CACHE_VERSION_KEY)
    except Exception:
        cache.set(HOMEPAGE_CACHE_VERSION_KEY, time.time_ns(), None)


def sync_legacy_lookbook_tags(sender, instance, action, reverse, pk_set, **kwargs):
    if reverse:
        invalidate_homepage_cache()
        return
    if action == 'post_clear':
        LookbookHotspot.objects.filter(card=instance).delete()
    elif action == 'post_remove':
        LookbookHotspot.objects.filter(card=instance, product_id__in=pk_set or []).delete()
    elif action == 'post_add':
        next_order = LookbookHotspot.objects.filter(card=instance).count()
        for product_id in sorted(pk_set or []):
            _, created = LookbookHotspot.objects.get_or_create(
                card=instance, product_id=product_id, defaults={'order': next_order}
            )
            if created:
                next_order += 1
    if action.startswith('post_'):
        invalidate_homepage_cache()


def sync_hotspot_to_legacy(sender, instance, **kwargs):
    instance.card.tagged_products.add(instance.product_id)


def remove_hotspot_from_legacy(sender, instance, **kwargs):
    instance.card.tagged_products.remove(instance.product_id)


HOMEPAGE_MODELS = [
    BannerSlide, PromoBar, StoreSettings, MegaMenuSection, MegaMenuSectionCategory,
    CollectionsMenuColumn, CollectionsMenuLink, CollectionsMenuPromo,
    NewInShowcaseCard, NewInShowcaseSettings, OutfitHighlightItem, LayeredScrollingCard, LookbookCard,
    ProductsHighlightSection, ProductSuggestionSection, ProductSuggestionStep,
    ProductsBundleSection, TestimonialsParallaxSection, TestimonialItem,
    OurStorySection, BrandPillarItem, FlexCarouselSection, FlexCarouselCard,
    ShopMenuPromo, PagesMenuSetting, PagesMenuCard, PagesMenuLink,
    FeaturesMenuItem, FeaturesMenuSubItem, LookbookHotspot, MarqueeItem,
    TrustBadge, FooterSettings, FooterLink, FooterInstagramImage, HeaderMenuItem,
    Product, Category, ProductImage, ProductVariant, Tag,
    SmartCollection, SmartCollectionRule, SmartCollectionPin,
    SmartCollectionHide, SmartCollectionManualProduct,
]


def register_homepage_signals():
    for model in HOMEPAGE_MODELS:
        post_save.connect(
            invalidate_homepage_cache,
            sender=model,
            dispatch_uid=f'invalidate_hp_save_{model.__name__}',
        )
        post_delete.connect(
            invalidate_homepage_cache,
            sender=model,
            dispatch_uid=f'invalidate_hp_del_{model.__name__}',
        )
    m2m_changed.connect(
        sync_legacy_lookbook_tags,
        sender=LookbookCard.tagged_products.through,
        dispatch_uid='sync_legacy_lookbook_tags',
    )
    for through in (
        ProductsHighlightSection.carousel_products.through,
        ProductSuggestionStep.products.through,
        ProductsBundleSection.bundle_products.through,
    ):
        m2m_changed.connect(
            invalidate_homepage_cache, sender=through,
            dispatch_uid=f'invalidate_hp_m2m_{through.__name__}',
        )
    post_save.connect(sync_hotspot_to_legacy, sender=LookbookHotspot, dispatch_uid='sync_hotspot_to_legacy')
    post_delete.connect(remove_hotspot_from_legacy, sender=LookbookHotspot, dispatch_uid='remove_hotspot_from_legacy')
