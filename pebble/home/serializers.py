from rest_framework import serializers 
from .models import (
    BannerSlide, PromoBar, CollectionsMenuColumn, CollectionsMenuPromo,
    MegaMenuSection, StoreSettings, NewInShowcaseCard, NewInShowcaseSettings, OutfitHighlightItem,
    LayeredScrollingCard, LookbookCard, ProductsHighlightSection,
    ProductSuggestionSection, ProductSuggestionStep,
    ProductsBundleSection, TestimonialsParallaxSection, TestimonialItem,
    OurStorySection, BrandPillarItem, FlexCarouselSection, FlexCarouselCard,
    ShopMenuPromo, LookbookHotspot, MarqueeItem, TrustBadge,
    FooterSettings, FooterLink, FooterInstagramImage, HeaderMenuItem
)
from products.serializers import ProductSerializer
from products.models import Category


class StoreSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreSettings
        fields = ['store_name', 'logo', 'contact_email', 'hero_transition']


class BannerSlideSerializer(serializers.ModelSerializer):
    class Meta:
        model = BannerSlide
        fields = ['id', 'title', 'subtitle', 'image', 'cta_text', 'cta_link', 'bg_color', 'order', 'destination_product_id', 'destination_collection_id']


class PromoBarSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoBar
        fields = ['id', 'text']


class FeaturedCategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'image', 'gender', 'display_count', 'product_count']

    def get_product_count(self, obj):
        if hasattr(obj, 'active_count'):
            return obj.active_count
        return obj.products.filter(is_active=True).count() 


class NewInShowcaseCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewInShowcaseCard
        fields = ['id', 'title', 'price', 'lifestyle_image', 'thumbnail_image', 'product_link', 'order', 'destination_product_id', 'destination_collection_id']


class NewInShowcaseSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewInShowcaseSettings
        fields = ['id', 'button_text', 'cta_link', 'is_active', 'destination_collection_id']


class OutfitHighlightItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutfitHighlightItem
        fields = [
            'id', 'title', 'subheading', 'heading', 'description',
            'thumbnail_image', 'lifestyle_image', 'button_text', 'link_url', 'order', 'destination_product_id', 'destination_collection_id'
        ]


class CollectionsMenuLinkSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    route = serializers.CharField()
    order = serializers.IntegerField()

class CollectionsMenuColumnSerializer(serializers.ModelSerializer):
    links = CollectionsMenuLinkSerializer(many=True)

    class Meta:
        model = CollectionsMenuColumn
        fields = ['id', 'title', 'order', 'links']


class CollectionsMenuPromoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectionsMenuPromo
        fields = ['id', 'title', 'image', 'route', 'order']


class ShopMenuPromoSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ShopMenuPromo
        fields = ['id', 'section', 'eyebrow', 'title', 'cta_text', 'cta_link', 'image', 'bg_color', 'is_active']

    def get_image(self, obj):
        request = self.context.get('request')
        url = obj.image.url if obj.image else None
        if url and request:
            return request.build_absolute_uri(url)
        return url



class LayeredScrollingCardSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = LayeredScrollingCard
        fields = ['id', 'label', 'subheading', 'heading', 'image', 'button_text', 'link_url', 'order']

    def get_image(self, obj):
        request = self.context.get('request')
        url = obj.image.url if obj.image else None
        if url and request:
            return request.build_absolute_uri(url)
        return url


class LookbookCardSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    tagged_products = ProductSerializer(many=True, read_only=True)
    hotspots = serializers.SerializerMethodField()

    class Meta:
        model = LookbookCard
        fields = ['id', 'title', 'image', 'item_count_label', 'tagged_products', 'hotspots', 'order']

    def get_hotspots(self, obj):
        hotspots = [hotspot for hotspot in obj.hotspots.all() if hotspot.product.is_active]
        return LookbookHotspotSerializer(hotspots, many=True, context=self.context).data

    def get_image(self, obj):
        request = self.context.get('request')
        url = obj.image.url if obj.image else None
        if url and request:
            return request.build_absolute_uri(url)
        return url


class LookbookHotspotSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = LookbookHotspot
        fields = ['id', 'product', 'desktop_x', 'desktop_y', 'mobile_x', 'mobile_y', 'order']


class MarqueeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarqueeItem
        fields = ['id', 'text', 'order', 'is_active']


class HeaderMenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = HeaderMenuItem
        fields = ['id', 'key', 'label', 'order', 'is_active']


class TrustBadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrustBadge
        fields = ['id', 'icon_key', 'title', 'subtitle', 'order', 'is_active']


class FooterSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterSettings
        fields = ['id', 'newsletter_heading', 'newsletter_disclaimer', 'copyright_text',
                  'instagram_heading', 'instagram_handle', 'instagram_url', 'x_url',
                  'tiktok_url', 'pinterest_url', 'is_active']


class FooterLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterLink
        fields = ['id', 'column', 'label', 'route', 'product_id', 'collection_id', 'order', 'is_active']


class FooterInstagramImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterInstagramImage
        fields = ['id', 'image', 'alt_text', 'order']


class ProductsHighlightSerializer(serializers.ModelSerializer):
    banner_image = serializers.SerializerMethodField()
    video_poster = serializers.SerializerMethodField()
    carousel_products = serializers.SerializerMethodField()

    class Meta:
        model = ProductsHighlightSection
        fields = [
            'id', 'tag', 'heading', 'description', 'button_text', 'button_link',
            'banner_image', 'video_url', 'video_poster', 'carousel_products'
        ]

    def get_banner_image(self, obj):
        request = self.context.get('request')
        url = obj.banner_image.url if obj.banner_image else None
        if url and request:
            return request.build_absolute_uri(url)
        return url

    def get_video_poster(self, obj):
        request = self.context.get('request')
        url = obj.video_poster.url if obj.video_poster else None
        if url and request:
            return request.build_absolute_uri(url)
        return url

    def get_carousel_products(self, obj):
        products = [p for p in obj.carousel_products.all() if p.is_active]
        products.sort(key=lambda p: 0 if 'hoodie' in p.slug else 1)
        return ProductSerializer(products, many=True, context=self.context).data


class ProductSuggestionStepSerializer(serializers.ModelSerializer):
    products = serializers.SerializerMethodField()

    class Meta:
        model = ProductSuggestionStep
        fields = [
            'id', 'step_number', 'title', 'badge_1', 'badge_2', 'products', 'order'
        ]

    def get_products(self, obj):
        products = sorted([p for p in obj.products.all() if p.is_active], key=lambda p: p.id)
        return ProductSerializer(products, many=True, context=self.context).data


class ProductSuggestionSerializer(serializers.ModelSerializer):
    steps = serializers.SerializerMethodField()

    class Meta:
        model = ProductSuggestionSection
        fields = ['id', 'tag', 'heading', 'steps']

    def get_steps(self, obj):
        steps = sorted((step for step in obj.steps.all() if step.is_active),
                       key=lambda step: (step.order, step.step_number))
        return ProductSuggestionStepSerializer(steps, many=True, context=self.context).data


class ProductsBundleSerializer(serializers.ModelSerializer):
    banner_image = serializers.SerializerMethodField()
    bundle_products = serializers.SerializerMethodField()

    class Meta:
        model = ProductsBundleSection
        fields = [
            'id', 'tag', 'heading', 'discount_percentage', 'banner_image',
            'hotspot_1_x', 'hotspot_1_y', 'hotspot_2_x', 'hotspot_2_y',
            'bundle_products', 'button_text'
        ]

    def get_banner_image(self, obj):
        request = self.context.get('request')
        url = obj.banner_image.url if obj.banner_image else None
        if url and request:
            return request.build_absolute_uri(url)
        return url

    def get_bundle_products(self, obj):
        products = [p for p in obj.bundle_products.all() if p.is_active]
        products.sort(key=lambda p: 0 if 'crochet' in p.slug else 1)
        return ProductSerializer(products, many=True, context=self.context).data


class TestimonialItemSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()

    class Meta:
        model = TestimonialItem
        fields = ['id', 'author', 'quote', 'rating', 'image', 'product', 'column_index', 'order']

    def get_image(self, obj):
        request = self.context.get('request')
        url = obj.image.url if obj.image else None
        if url and request:
            return request.build_absolute_uri(url)
        return url

    def get_product(self, obj):
        if not obj.product:
            return None
        return ProductSerializer(obj.product, context=self.context).data


class TestimonialsParallaxSerializer(serializers.ModelSerializer):
    testimonials = serializers.SerializerMethodField()

    class Meta:
        model = TestimonialsParallaxSection
        fields = ['id', 'tag', 'heading', 'testimonials']

    def get_testimonials(self, obj):
        items = sorted((item for item in obj.testimonials.all() if item.is_active), key=lambda t: t.order)
        return TestimonialItemSerializer(items, many=True, context=self.context).data


class OurStorySerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = OurStorySection
        fields = [
            'id', 'tag', 'heading', 'description', 'button_text', 'button_link',
            'image', 'badge_1_text', 'badge_1_color', 'badge_2_text', 'badge_2_color'
        ]

    def get_image(self, obj):
        request = self.context.get('request')
        url = obj.image.url if obj.image else None
        if url and request:
            return request.build_absolute_uri(url)
        return url


class BrandPillarItemSerializer(serializers.ModelSerializer):
    icon = serializers.SerializerMethodField()

    class Meta:
        model = BrandPillarItem
        fields = ['id', 'title', 'icon', 'button_text', 'button_link', 'order']

    def get_icon(self, obj):
        request = self.context.get('request')
        url = obj.icon.url if obj.icon else None
        if url and request:
            return request.build_absolute_uri(url)
        return url


class FlexCarouselCardSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = FlexCarouselCard
        fields = [
            'id', 'badge', 'heading', 'subtext', 'image',
            'width_desktop_percent', 'link', 'order'
        ]

    def get_image(self, obj):
        request = self.context.get('request')
        url = obj.image.url if obj.image else None
        if url and request:
            return request.build_absolute_uri(url)
        return url


class FlexCarouselSectionSerializer(serializers.ModelSerializer):
    cards = serializers.SerializerMethodField()

    class Meta:
        model = FlexCarouselSection
        fields = ['id', 'heading', 'cards']

    def get_cards(self, obj):
        cards = sorted([c for c in obj.cards.all() if c.is_active], key=lambda c: c.order)
        return FlexCarouselCardSerializer(cards, many=True, context=self.context).data


class HomePageSerializer(serializers.Serializer):
    store_settings = StoreSettingsSerializer(allow_null=True, required=False)
    promo_bar = PromoBarSerializer(allow_null=True)
    banners = BannerSlideSerializer(many=True)
    featured_categories = FeaturedCategorySerializer(many=True)
    new_in_showcase = NewInShowcaseCardSerializer(many=True)
    new_in_showcase_settings = NewInShowcaseSettingsSerializer(allow_null=True, required=False)
    outfit_highlights = OutfitHighlightItemSerializer(many=True)
    layered_cards = LayeredScrollingCardSerializer(many=True)
    lookbook_cards = LookbookCardSerializer(many=True, required=False)
    products_highlight = ProductsHighlightSerializer(allow_null=True, required=False)
    product_suggestion = ProductSuggestionSerializer(allow_null=True, required=False)
    products_bundle = ProductsBundleSerializer(allow_null=True, required=False)
    testimonials_parallax = TestimonialsParallaxSerializer(allow_null=True, required=False)
    our_story = OurStorySerializer(allow_null=True, required=False)
    brand_pillars = BrandPillarItemSerializer(many=True, required=False)
    flex_carousel = FlexCarouselSectionSerializer(allow_null=True, required=False)
    new_arrivals = ProductSerializer(many=True)
    best_sellers = ProductSerializer(many=True)
    shop_menu = serializers.DictField()
    collections_menu = serializers.DictField()
    pages_menu = serializers.DictField(required=False)
    features_menu = serializers.ListField(required=False)
    marquee_items = MarqueeItemSerializer(many=True, required=False)
    header_menu = HeaderMenuItemSerializer(many=True, required=False)
    trust_badges = TrustBadgeSerializer(many=True, required=False)
    footer_settings = FooterSettingsSerializer(allow_null=True, required=False)
    footer_links = FooterLinkSerializer(many=True, required=False)
    footer_instagram_images = FooterInstagramImageSerializer(many=True, required=False)
