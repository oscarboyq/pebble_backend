from django.db import models
from django.conf import settings


class MediaRightsRecord(models.Model):
    """Owner attestation for a referenced media path; the file remains untouched."""
    path = models.CharField(max_length=500, unique=True)
    source_url = models.URLField(blank=True)
    rights_holder = models.CharField(max_length=200, blank=True)
    permission_note = models.TextField(blank=True)
    approved_for_public = models.BooleanField(default=False)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.approved_for_public and not (self.rights_holder.strip() and self.permission_note.strip()):
            raise ValidationError({'approved_for_public': 'Rights holder and permission evidence are required.'})

    def __str__(self):
        return self.path


class BannerSlide(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    title = models.CharField(max_length=200,blank=True)
    subtitle = models.CharField(max_length=300,blank=True)
    image = models.ImageField(upload_to='banners/')
    cta_text = models.CharField(max_length=100, blank=True)
    cta_link = models.CharField(max_length=255, blank=True)
    bg_color = models.CharField(max_length=30, default='#C99484', blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)


    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return f'Banner: {self.title} (order={self.order})'
    

class PromoBar(models.Model):
    text = models.CharField(max_length=300)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.text


class StoreSettings(models.Model):
    """Singleton — always use pk=1 via get_or_create."""
    HERO_TRANSITION_CHOICES = [
        ('fade_zoom', 'Fade & Gentle Zoom (Ken Burns)'),
        ('slide', 'Horizontal Slide'),
    ]

    store_name = models.CharField(max_length=200, default='My Store')
    logo = models.ImageField(upload_to='store/', blank=True, null=True)
    contact_email = models.EmailField(blank=True, default='')
    promo_bar_text = models.CharField(max_length=300, blank=True, default='')
    promo_bar_enabled = models.BooleanField(default=False)
    hero_transition = models.CharField(
        max_length=30,
        choices=HERO_TRANSITION_CHOICES,
        default='fade_zoom',
    )

    def __str__(self):
        return self.store_name
    

from products.models import Category 

class MegaMenuSection(models.Model): 
    SECTION_NEW_ARRIVALS = 'new_arrivals'
    SECTION_BEST_SELLERS = 'best_sellers'
    SECTION_CLOTHING = 'clothing'
    SECTION_SHOP_ALL = 'shop_all'

    SECTION_CHOICES = [
        (SECTION_NEW_ARRIVALS, 'New Arrivals'),
        (SECTION_BEST_SELLERS, 'Best Sellers'),
        (SECTION_CLOTHING, 'Clothing'),
        (SECTION_SHOP_ALL, 'Shop All'),
    ]

    key = models.CharField(max_length=50, choices=SECTION_CHOICES, unique=True)
    title = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    use_manual_categories = models.BooleanField(default=False) 

    DISPLAY_CATEGORIES = 'categories'
    DISPLAY_PRODUCTS = 'products'
    DISPLAY_CHOICES = [
        (DISPLAY_CATEGORIES, 'Categories'),
        (DISPLAY_PRODUCTS, 'Products'),
    ]

    smart_collection = models.ForeignKey(
        'collections.SmartCollection',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='mega_menu_sections',
    )
    display_mode = models.CharField(
        max_length=12,
        choices=DISPLAY_CHOICES,
        default=DISPLAY_CATEGORIES,
    )

    def __str__(self):
        return self.title 
    

class MegaMenuSectionCategory(models.Model):
    section = models.ForeignKey(
        MegaMenuSection,
        on_delete=models.CASCADE,
        related_name='category_items',
    )
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)
    image_override = models.ImageField(upload_to='menu_category_images/', blank=True, null=True)

    class Meta:
        ordering = ['order']
        unique_together = ('section', 'category')

    def __str__(self):
        return f'{self.section.title} - {self.category.name}'
    

    
class CollectionsMenuColumn(models.Model):
    title = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return self.title
    


class CollectionsMenuLink(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    column = models.ForeignKey(
        CollectionsMenuColumn,
        on_delete=models.CASCADE,
        related_name='links',
    )
    label = models.CharField(max_length=100)
    route = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['column', 'order']),
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return f'{self.column.title} - {self.label}'
    

class CollectionsMenuPromo(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    title = models.CharField(max_length=120)
    image = models.ImageField(upload_to='collections_menu/')
    route = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return self.title


class NewInShowcaseSettings(models.Model):
    """Owner-managed CTA for the center of the New In showcase."""
    destination_collection = models.ForeignKey(
        'collections.SmartCollection', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    button_text = models.CharField(max_length=50, default='Shop Now')
    cta_link = models.CharField(max_length=255, default='/collections/outerwear', editable=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'New In button: {self.button_text}'


class NewInShowcaseCard(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    title = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    lifestyle_image = models.ImageField(upload_to='showcase_images/')
    thumbnail_image = models.ImageField(upload_to='showcase_images/', blank=True, null=True)
    product_link = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return f'{self.title} (${self.price})'


class OutfitHighlightItem(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    title = models.CharField(max_length=100)
    subheading = models.CharField(max_length=150)
    heading = models.CharField(max_length=255)
    description = models.TextField()
    thumbnail_image = models.ImageField(upload_to='highlight_images/')
    lifestyle_image = models.ImageField(upload_to='highlight_images/')
    button_text = models.CharField(max_length=50, default='Shop Now')
    link_url = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return f'{self.title} - {self.subheading}'


class LayeredScrollingCard(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    label = models.CharField(max_length=100)
    subheading = models.CharField(max_length=150)
    heading = models.CharField(max_length=200)
    image = models.ImageField(upload_to='layered_cards/')
    button_text = models.CharField(max_length=50, default='Shop now')
    link_url = models.CharField(max_length=255, default='/collections/all')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return f'{self.heading} ({self.label})'


class LookbookCard(models.Model):
    title = models.CharField(max_length=120)
    image = models.ImageField(upload_to='lookbook_cards/')
    item_count_label = models.CharField(max_length=50, default='2 items')
    tagged_products = models.ManyToManyField(
        'products.Product',
        blank=True,
        related_name='lookbook_cards',
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return f'{self.title} ({self.item_count_label})'


class LookbookHotspot(models.Model):
    card = models.ForeignKey(LookbookCard, on_delete=models.CASCADE, related_name='hotspots')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='lookbook_hotspots')
    desktop_x = models.FloatField(null=True, blank=True)
    desktop_y = models.FloatField(null=True, blank=True)
    mobile_x = models.FloatField(null=True, blank=True)
    mobile_y = models.FloatField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        constraints = [models.UniqueConstraint(fields=['card', 'product'], name='unique_lookbook_hotspot_product')]

    def clean(self):
        from django.core.exceptions import ValidationError
        for name in ('desktop_x', 'desktop_y', 'mobile_x', 'mobile_y'):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 100:
                raise ValidationError({name: 'Coordinate must be between 0 and 100.'})
        if (self.desktop_x is None) != (self.desktop_y is None):
            raise ValidationError('Desktop coordinates must be supplied together.')
        if (self.mobile_x is None) != (self.mobile_y is None):
            raise ValidationError('Mobile coordinates must be supplied together.')


class MarqueeItem(models.Model):
    text = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'id']


class HeaderMenuItem(models.Model):
    key = models.CharField(max_length=30, unique=True, choices=[
        ('shop', 'Shop'), ('collections', 'Collections'),
        ('pages', 'Pages'), ('features', 'Features'),
    ])
    label = models.CharField(max_length=80)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'id']


class TrustBadge(models.Model):
    icon_key = models.CharField(max_length=60, choices=[
        ('delivery', 'Delivery'), ('returns', 'Returns'),
        ('payment', 'Payment'), ('service', 'Service'),
    ])
    title = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=240, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'id']


class FooterSettings(models.Model):
    newsletter_heading = models.CharField(max_length=255, default='Subscribe for updates, tips & exclusive offers')
    newsletter_disclaimer = models.TextField(blank=True)
    copyright_text = models.CharField(max_length=255, default='© 2026 Pebble Little')
    instagram_heading = models.CharField(max_length=120, default='Follow Us on Instagram')
    instagram_handle = models.CharField(max_length=100, default='@littlepebble.co')
    instagram_url = models.URLField(blank=True)
    x_url = models.URLField(blank=True)
    tiktok_url = models.URLField(blank=True)
    pinterest_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)


class FooterLink(models.Model):
    column = models.CharField(max_length=50, choices=[('company', 'Company'), ('collection', 'Collection'), ('help', 'Get Help'), ('legal', 'Legal')])
    label = models.CharField(max_length=100)
    route = models.CharField(max_length=255, blank=True)
    collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL)
    product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['column', 'order', 'id']

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.collection_id and self.product_id:
            raise ValidationError('Choose a product or collection, not both.')


class FooterInstagramImage(models.Model):
    image = models.ImageField(upload_to='footer_instagram/')
    alt_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'id']


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=40, default='footer')

    class Meta:
        ordering = ['-subscribed_at']


class ProductsHighlightSection(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    tag = models.CharField(max_length=100, default='HOT ITEMS')
    heading = models.CharField(max_length=255, default='Shop The Winter\nSet')
    description = models.TextField(
        default='Comfortably wear Oura Ring all day and night to collect deeply personal health metrics.'
    )
    button_text = models.CharField(max_length=50, default='Shop now')
    button_link = models.CharField(max_length=255, default='/products/denim-jeans-kids')
    banner_image = models.ImageField(upload_to='highlight_banners/')
    video_url = models.CharField(max_length=500, blank=True)
    video_poster = models.ImageField(upload_to='highlight_posters/', blank=True, null=True)
    carousel_products = models.ManyToManyField(
        'products.Product',
        blank=True,
        related_name='highlight_sections',
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.heading.replace('\n', ' ')


class ProductSuggestionSection(models.Model):
    tag = models.CharField(max_length=100, default='How you style it')
    heading = models.TextField(default='Dress up in 3 steps.\nPick - Pair - Play!')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.tag} - {self.heading.replace(chr(10), " ")}'


class ProductSuggestionStep(models.Model):
    section = models.ForeignKey(
        ProductSuggestionSection,
        on_delete=models.CASCADE,
        related_name='steps',
    )
    step_number = models.PositiveSmallIntegerField(default=1)
    title = models.CharField(max_length=255)
    badge_1 = models.CharField(max_length=100, blank=True)
    badge_2 = models.CharField(max_length=100, blank=True)
    products = models.ManyToManyField(
        'products.Product',
        blank=True,
        related_name='suggestion_steps',
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'step_number']
        indexes = [
            models.Index(fields=['section', 'order']),
        ]

    def __str__(self):
        return f'Step {self.step_number}: {self.title}'


class ProductsBundleSection(models.Model):
    tag = models.CharField(max_length=100, default='Bundle & Save')
    heading = models.CharField(max_length=255, default='Buy 2 Get 10% Off')
    discount_percentage = models.PositiveIntegerField(default=10)
    banner_image = models.ImageField(upload_to='bundle_banners/')
    hotspot_1_x = models.FloatField(default=56.0)
    hotspot_1_y = models.FloatField(default=26.0)
    hotspot_2_x = models.FloatField(default=40.0)
    hotspot_2_y = models.FloatField(default=62.0)
    bundle_products = models.ManyToManyField(
        'products.Product',
        blank=True,
        related_name='bundle_sections',
    )
    button_text = models.CharField(max_length=100, default='Add all to cart')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.tag} - {self.heading}'


class TestimonialsParallaxSection(models.Model):
    tag = models.CharField(max_length=100, default='What customers say')
    heading = models.CharField(max_length=255, default='Over 500\nHappy Reviews')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.tag} - {self.heading.replace(chr(10), " ")}'


class TestimonialItem(models.Model):
    section = models.ForeignKey(
        TestimonialsParallaxSection,
        on_delete=models.CASCADE,
        related_name='testimonials',
    )
    author = models.CharField(max_length=100)
    quote = models.TextField()
    rating = models.PositiveSmallIntegerField(default=5)
    image = models.ImageField(upload_to='testimonial_images/')
    product = models.ForeignKey(
        'products.Product',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='testimonials',
    )
    column_index = models.PositiveSmallIntegerField(default=0)  # 0=left, 1=center, 2=right
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['section', 'order']),
        ]

    def __str__(self):
        return f'{self.author} ({self.rating} stars)'


class OurStorySection(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    tag = models.CharField(max_length=100, default='our story')
    heading = models.CharField(max_length=255, default='Delicate ruffles with soft finishes.')
    description = models.TextField(
        default='Designed with movement in mind, our pieces offer breathable comfort and relaxed silhouettes. '
                'Subtle details add personality without compromising ease. Carefully crafted details bring a '
                'playful touch while staying soft against the skin.'
    )
    button_text = models.CharField(max_length=50, default='Learn more')
    button_link = models.CharField(max_length=255, default='/pages/our-journal')
    image = models.ImageField(upload_to='story_images/')
    badge_1_text = models.CharField(max_length=50, default='Wow')
    badge_1_color = models.CharField(max_length=30, default='#BDE6EE')
    badge_2_text = models.CharField(max_length=50, default='Playful')
    badge_2_color = models.CharField(max_length=30, default='#FFC8C8')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.tag} - {self.heading}'


class BrandPillarItem(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    title = models.CharField(max_length=100)
    icon = models.ImageField(upload_to='brand_pillars/')
    button_text = models.CharField(max_length=50, default='shop')
    button_link = models.CharField(max_length=255, default='/collections/all')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return self.title


class FlexCarouselSection(models.Model):
    heading = models.CharField(max_length=255, default='Dress your explorer in comfort')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.heading


class FlexCarouselCard(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    section = models.ForeignKey(
        FlexCarouselSection,
        on_delete=models.CASCADE,
        related_name='cards',
    )
    badge = models.CharField(max_length=50, blank=True)
    heading = models.CharField(max_length=255)
    subtext = models.TextField(blank=True)
    image = models.ImageField(upload_to='flex_carousel_cards/')
    width_desktop_percent = models.PositiveSmallIntegerField(default=30)
    link = models.CharField(max_length=255, default='/collections/all')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['section', 'order']),
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return f'{self.heading} ({self.badge})'


class ShopMenuPromo(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    SECTION_CHOICES = [
        ('new_arrivals', 'New Arrivals'),
        ('best_sellers', 'Best Sellers'),
        ('clothing', 'Clothing'),
        ('shop_all', 'Shop All'),
    ]
    section = models.CharField(
        max_length=50,
        choices=SECTION_CHOICES,
        default='new_arrivals',
        unique=True,
        help_text='Header Shop menu section to which this promo belongs',
    )
    eyebrow = models.CharField(max_length=100, default='NEW COLLECTION')
    title = models.CharField(max_length=200, default='The Cozy Crew')
    cta_text = models.CharField(max_length=80, default='Shop Now')
    cta_link = models.CharField(max_length=255, default='/products')
    image = models.ImageField(upload_to='menu_promos/', blank=True, null=True)
    bg_color = models.CharField(max_length=50, default='#84A999')
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Shop Menu Promo'
        verbose_name_plural = 'Shop Menu Promos'

    def __str__(self):
        return f'{self.get_section_display()}: {self.title} ({self.eyebrow})'



class PagesMenuSetting(models.Model):
    """Singleton for Pages mega menu headline and philosophy text"""
    who_we_are_title = models.CharField(max_length=150, default='Who We Are')
    who_we_are_text = models.TextField(
        default='We create simple, well-made essentials that balance comfort and style, giving kids the freedom to explore, play, and grow every day.'
    )

    def __str__(self):
        return self.who_we_are_title


class PagesMenuCard(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    title = models.CharField(max_length=120)
    image = models.ImageField(upload_to='pages_menu/')
    route = models.CharField(max_length=255, default='/pages/our-story')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class PagesMenuLink(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    label = models.CharField(max_length=100)
    route = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.label


class FeaturesMenuItem(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    title = models.CharField(max_length=120)
    route = models.CharField(max_length=255, default='/collections')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class FeaturesMenuSubItem(models.Model):
    destination_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    destination_collection = models.ForeignKey('collections.SmartCollection', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    parent = models.ForeignKey(
        FeaturesMenuItem,
        on_delete=models.CASCADE,
        related_name='sub_items',
    )
    title = models.CharField(max_length=120)
    route = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.parent.title} -> {self.title}'
