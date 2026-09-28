from django.db import models
from django.db.models import F, Q
from django.contrib.auth.models import User


class Category(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True) 
    image = models.ImageField(upload_to='category_images/', blank=True, null=True)
    banner_image = models.ImageField(upload_to='category_banners/', blank=True, null=True)
    gender = models.CharField(max_length=20, default='boys', choices=[('boys', "Boy's"), ('girls', "Girl's"), ('all', 'All')])
    display_count = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_featured', 'id']),
            models.Index(fields=['gender', 'is_featured']),
        ]

    def __str__(self):
        return f'{self.name} ({self.gender}) - Category' 
    

class Tag(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    id = models.AutoField(primary_key=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products') 
    product_type = models.CharField(max_length=80, blank=True, db_index=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sku = models.CharField(max_length=100, blank=True)
    badge = models.CharField(max_length=50, blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name='products')
    video_url = models.URLField(blank=True)
    video_file = models.FileField(upload_to='product_videos/', blank=True, null=True)
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) 
    is_active = models.BooleanField(default=True)

    # Product detail / spec fields
    material = models.CharField(max_length=200, blank=True, default='')
    material_source = models.TextField(blank=True, default='')
    material_verified_at = models.DateTimeField(null=True, blank=True)
    material_verified_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='verified_product_materials')
    special_features = models.TextField(blank=True, default='')
    care_and_cleaning = models.TextField(blank=True, default='')
    manufactured_by = models.CharField(max_length=200, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_active', '-created_at']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['is_active', 'slug']),
        ]

    def __str__(self):
        return f'{self.name} - Product' 

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.material_verified_at and not (self.material.strip() and self.material_source.strip()):
            raise ValidationError({'material_verified_at': 'Material and its evidence are required.'})


class ProductImage(models.Model):
    id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    images = models.ImageField(upload_to='product_images/')
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['product', 'order']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['product'], condition=Q(is_primary=True), name='one_primary_image_per_product'),
        ]

    def __str__(self):
        return f'Image for {self.product.name} - {self.alt_text}' 

    def save(self, *args, **kwargs):
        old_name = None
        if self.pk:
            old_name = type(self).objects.filter(pk=self.pk).values_list('images', flat=True).first()
        super().save(*args, **kwargs)
        # Metadata-only edits reuse the derivative. New uploads get one at save.
        if old_name != self.images.name:
            from .card_images import ensure_card_image
            ensure_card_image(self)


class ProductLink(models.Model):
    """Ordered, directed owner selection for product discovery."""
    INTENTS = [('outfit', 'Outfit'), ('related', 'Related'), ('complementary', 'Complementary')]
    source = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='outgoing_links')
    target = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='incoming_links')
    intent = models.CharField(max_length=20, choices=INTENTS)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['source', 'intent', 'target'], name='unique_product_link'),
            models.CheckConstraint(condition=~Q(source=F('target')), name='product_link_no_self'),
        ]
        indexes = [models.Index(fields=['source', 'intent', 'order'])]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.source_id and self.source_id == self.target_id:
            raise ValidationError('A product cannot link to itself.')
    

class ProductVariant(models.Model):
    id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    color = models.CharField(max_length=50, blank=True)
    size = models.CharField(max_length=50, blank=True)
    stock = models.PositiveIntegerField(default=0)
    price_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    attributes = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Variant of {self.product.name} - Color: {self.color}, Size: {self.size}'
    



class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField()  # 1–5
    title = models.CharField(max_length=150, blank=True)
    body = models.TextField(blank=True)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')  # one review per user per product
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} → {self.product.name} ({self.rating}★)'
    

class CategoryVariantTemplate(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='variant_templates')
    name = models.CharField(max_length=100)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'name'] 
        unique_together = ('category', 'name') 

    def __str__ (self):
        return f'{self.category.name} → {self.name}'
    

class CategoryVariantOption(models.Model):
    template = models.ForeignKey(CategoryVariantTemplate, on_delete=models.CASCADE, related_name='options')
    value = models.CharField(max_length=100)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'value'] 
        unique_together = ('template', 'value')


    def __str__(self):
        return f'{self.template.name}: {self.value}'
    







class SizeChart(models.Model):
    """A product size chart shown on the product detail page.

    ``columns`` is a list of column headers, ``rows`` a list of rows where each
    row is a list of cell values (aligned to ``columns``). ``note`` holds free
    guidance text such as how-to-measure instructions.
    """

    name = models.CharField(max_length=120, default='Default size chart')
    columns = models.JSONField(default=list, blank=True)
    rows = models.JSONField(default=list, blank=True)
    note = models.TextField(blank=True)
    image = models.ImageField(upload_to='size_charts/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
