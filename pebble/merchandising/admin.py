from django.contrib import admin

from .models import (
    SmartCollection,
    SmartCollectionHide,
    SmartCollectionManualProduct,
    SmartCollectionPin,
    SmartCollectionRule,
)


class SmartCollectionRuleInline(admin.TabularInline):
    model = SmartCollectionRule
    extra = 1


class SmartCollectionPinInline(admin.TabularInline):
    model = SmartCollectionPin
    extra = 1


class SmartCollectionHideInline(admin.TabularInline):
    model = SmartCollectionHide
    extra = 1


class SmartCollectionManualProductInline(admin.TabularInline):
    model = SmartCollectionManualProduct
    extra = 1


@admin.register(SmartCollection)
class SmartCollectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'collection_type', 'sort', 'limit', 'is_active']
    list_editable = ['is_active']
    list_filter = ['collection_type', 'is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [
        SmartCollectionRuleInline,
        SmartCollectionPinInline,
        SmartCollectionHideInline,
        SmartCollectionManualProductInline,
    ]
