from django.contrib import admin
from .models import (
    BannerSlide,
    PromoBar,
    NewInShowcaseCard,
    NewInShowcaseSettings,
    OutfitHighlightItem,
    LayeredScrollingCard,
    LookbookCard,
    ProductsHighlightSection,
    ProductSuggestionSection,
    ProductSuggestionStep,
    ProductsBundleSection,
    TestimonialsParallaxSection,
    TestimonialItem,
    OurStorySection,
    BrandPillarItem,
    FlexCarouselSection,
    FlexCarouselCard,
    MegaMenuSection,
    MegaMenuSectionCategory,
    CollectionsMenuColumn,
    CollectionsMenuLink,
    CollectionsMenuPromo,
    ShopMenuPromo,
    PagesMenuSetting,
    PagesMenuCard,
    PagesMenuLink,
    FeaturesMenuItem,
    FeaturesMenuSubItem,
    LookbookHotspot, MarqueeItem, TrustBadge, FooterSettings,
    FooterLink, FooterInstagramImage, NewsletterSubscriber, HeaderMenuItem,
    MediaRightsRecord,
)


@admin.register(MediaRightsRecord)
class MediaRightsRecordAdmin(admin.ModelAdmin):
    list_display = ['path', 'rights_holder', 'approved_for_public', 'reviewed_at']
    search_fields = ['path', 'rights_holder']


@admin.register(BannerSlide)
class BannerSlideAdmin(admin.ModelAdmin):
    list_display = ['title', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    ordering = ['order']


@admin.register(PromoBar)
class PromoBarAdmin(admin.ModelAdmin):
    list_display = ['text', 'is_active']
    list_editable = ['is_active']


@admin.register(NewInShowcaseCard)
class NewInShowcaseCardAdmin(admin.ModelAdmin):
    list_display = ['title', 'price', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    ordering = ['order']


@admin.register(NewInShowcaseSettings)
class NewInShowcaseSettingsAdmin(admin.ModelAdmin):
    list_display = ['button_text', 'destination_collection', 'is_active']


@admin.register(OutfitHighlightItem)
class OutfitHighlightItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'subheading', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    ordering = ['order']


@admin.register(LayeredScrollingCard)
class LayeredScrollingCardAdmin(admin.ModelAdmin):
    list_display = ['heading', 'label', 'subheading', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    ordering = ['order']


@admin.register(LookbookCard)
class LookbookCardAdmin(admin.ModelAdmin):
    list_display = ['title', 'item_count_label', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    ordering = ['order']
    filter_horizontal = ['tagged_products']


@admin.register(LookbookHotspot)
class LookbookHotspotAdmin(admin.ModelAdmin):
    list_display = ['card', 'product', 'desktop_x', 'desktop_y', 'mobile_x', 'mobile_y', 'order']
    autocomplete_fields = ['product']


@admin.register(MarqueeItem, TrustBadge, FooterSettings, FooterLink, FooterInstagramImage, NewsletterSubscriber, HeaderMenuItem)
class EditorialContentAdmin(admin.ModelAdmin):
    pass


@admin.register(ProductsHighlightSection)
class ProductsHighlightSectionAdmin(admin.ModelAdmin):
    list_display = ['heading', 'tag', 'is_active']
    list_editable = ['is_active']
    filter_horizontal = ['carousel_products']


class ProductSuggestionStepInline(admin.StackedInline):
    model = ProductSuggestionStep
    extra = 0
    filter_horizontal = ['products']


@admin.register(ProductSuggestionSection)
class ProductSuggestionSectionAdmin(admin.ModelAdmin):
    list_display = ['tag', 'heading', 'is_active']
    list_editable = ['is_active']
    inlines = [ProductSuggestionStepInline]


@admin.register(ProductSuggestionStep)
class ProductSuggestionStepAdmin(admin.ModelAdmin):
    list_display = ['step_number', 'title', 'badge_1', 'badge_2', 'order']
    list_editable = ['order']
    ordering = ['order', 'step_number']
    filter_horizontal = ['products']


@admin.register(ProductsBundleSection)
class ProductsBundleSectionAdmin(admin.ModelAdmin):
    list_display = ['heading', 'tag', 'discount_percentage', 'is_active']
    list_editable = ['is_active']
    filter_horizontal = ['bundle_products']


class TestimonialItemInline(admin.StackedInline):
    model = TestimonialItem
    extra = 0


@admin.register(TestimonialsParallaxSection)
class TestimonialsParallaxSectionAdmin(admin.ModelAdmin):
    list_display = ['tag', 'heading', 'is_active']
    list_editable = ['is_active']
    inlines = [TestimonialItemInline]


@admin.register(TestimonialItem)
class TestimonialItemAdmin(admin.ModelAdmin):
    list_display = ['author', 'rating', 'column_index', 'order']
    list_editable = ['order', 'column_index']
    ordering = ['order']


@admin.register(OurStorySection)
class OurStorySectionAdmin(admin.ModelAdmin):
    list_display = ['tag', 'heading', 'is_active']
    list_editable = ['is_active']


@admin.register(BrandPillarItem)
class BrandPillarItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'button_text', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    ordering = ['order']


class FlexCarouselCardInline(admin.TabularInline):
    model = FlexCarouselCard
    extra = 0
    fields = ['order', 'heading', 'badge', 'subtext', 'width_desktop_percent', 'image', 'link', 'is_active']


@admin.register(FlexCarouselSection)
class FlexCarouselSectionAdmin(admin.ModelAdmin):
    list_display = ['heading', 'is_active']
    list_editable = ['is_active']
    inlines = [FlexCarouselCardInline]


@admin.register(FlexCarouselCard)
class FlexCarouselCardAdmin(admin.ModelAdmin):
    list_display = ['heading', 'badge', 'width_desktop_percent', 'order', 'is_active']
    list_editable = ['order', 'width_desktop_percent', 'is_active']
    ordering = ['order']


# ── Shop Mega Menu ───────────────────────────────────────────────
class MegaMenuSectionCategoryInline(admin.TabularInline):
    model = MegaMenuSectionCategory
    extra = 1


@admin.register(MegaMenuSection)
class MegaMenuSectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'key', 'use_manual_categories', 'display_mode', 'smart_collection', 'is_active']
    list_editable = ['use_manual_categories', 'display_mode', 'is_active']
    inlines = [MegaMenuSectionCategoryInline]


@admin.register(ShopMenuPromo)
class ShopMenuPromoAdmin(admin.ModelAdmin):
    list_display = ['section', 'title', 'eyebrow', 'cta_text', 'bg_color', 'is_active']
    list_editable = ['is_active']
    list_filter = ['section', 'is_active']



# ── Collections Mega Menu ────────────────────────────────────────
class CollectionsMenuLinkInline(admin.TabularInline):
    model = CollectionsMenuLink
    extra = 1
    fields = ['label', 'route', 'order', 'is_active']


@admin.register(CollectionsMenuColumn)
class CollectionsMenuColumnAdmin(admin.ModelAdmin):
    list_display = ['title', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    ordering = ['order']
    inlines = [CollectionsMenuLinkInline]


@admin.register(CollectionsMenuPromo)
class CollectionsMenuPromoAdmin(admin.ModelAdmin):
    list_display = ['title', 'route', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    ordering = ['order']


# ── Pages Mega Menu ──────────────────────────────────────────────
@admin.register(PagesMenuSetting)
class PagesMenuSettingAdmin(admin.ModelAdmin):
    list_display = ['who_we_are_title']


@admin.register(PagesMenuCard)
class PagesMenuCardAdmin(admin.ModelAdmin):
    list_display = ['title', 'route', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    ordering = ['order']


@admin.register(PagesMenuLink)
class PagesMenuLinkAdmin(admin.ModelAdmin):
    list_display = ['label', 'route', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    ordering = ['order']


# ── Features Dropdown Menu ───────────────────────────────────────
class FeaturesMenuSubItemInline(admin.TabularInline):
    model = FeaturesMenuSubItem
    extra = 1
    fields = ['title', 'route', 'order', 'is_active']


@admin.register(FeaturesMenuItem)
class FeaturesMenuItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'route', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    ordering = ['order']
    inlines = [FeaturesMenuSubItemInline]
