from django.contrib import admin
from .models import Category, Product, ProductImage, ProductVariant, Review, Tag, ProductLink, SizeChart


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_featured']
    list_editable = ['is_featured']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'badge', 'is_active', 'created_at']
    list_editable = ['is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'sku']
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ['tags']


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(ProductLink)
class ProductLinkAdmin(admin.ModelAdmin):
    list_display = ['source', 'intent', 'target', 'order']
    list_filter = ['intent']
    autocomplete_fields = ['source', 'target']
    ordering = ['source_id', 'intent', 'order']


@admin.register(SizeChart)
class SizeChartAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'updated_at']
    list_editable = ['is_active']


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'alt_text', 'order', 'is_primary']
    list_editable = ['alt_text', 'order', 'is_primary']
    autocomplete_fields = ['product']
