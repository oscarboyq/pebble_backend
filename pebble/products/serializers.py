from .models import Product, Category, ProductImage, ProductVariant, Review, CategoryVariantTemplate, CategoryVariantOption, SizeChart
from rest_framework import serializers
from django.db.models import Avg


def approved_reviews(obj):
    """Return the product's approved reviews, using a prefetched cache if present."""
    cached = getattr(obj, '_prefetched_objects_cache', {}).get('reviews')
    if cached is not None:
        return [r for r in cached if r.is_approved]
    return list(obj.reviews.filter(is_approved=True))


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'image', 'banner_image', 'gender', 'display_count']


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'image', 'banner_image', 'gender', 'display_count', 'is_featured', 'product_count']

    def get_product_count(self, obj):
        if hasattr(obj, 'active_count'):
            return obj.active_count
        return obj.products.filter(is_active=True).count()


class AdminCategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'image', 'banner_image', 'gender', 'display_count', 'is_featured', 'product_count']

    def get_product_count(self, obj):
        if hasattr(obj, 'active_count'):
            return obj.active_count
        return obj.products.filter(is_active=True).count()


class CategoryVariantTemplateSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()

    class Meta:
        model = CategoryVariantTemplate
        fields = ['id', 'category', 'name', 'display_order', 'options', 'created_at']
        read_only_fields = ['category', 'created_at']

    def get_options(self, obj):
        return [
            {
               'id': opt.id,
                'value': opt.value,
                'display_order': opt.display_order,
            }
            for opt in obj.options.all()
        ]


class CategoryVariantOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryVariantOption
        fields = ['id', 'template', 'value', 'display_order', 'created_at']
        read_only_fields = ['template', 'created_at']



class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    card_image = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'card_image', 'alt_text', 'is_primary', 'order']

    def get_image(self, obj):
        request = self.context.get('request')
        url = obj.images.url if obj.images else None
        if url and request:
            return request.build_absolute_uri(url)
        return url

    def get_card_image(self, obj):
        from .card_images import card_image_url
        url = card_image_url(obj)
        request = self.context.get('request')
        return request.build_absolute_uri(url) if url and request else url


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ['id', 'color', 'size', 'stock', 'price_override', 'attributes']


class ProductSerializer(serializers.ModelSerializer):
    material = serializers.SerializerMethodField()
    material_source = serializers.SerializerMethodField()
    material_verified = serializers.SerializerMethodField()
    category = ProductCategorySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    video_file = serializers.SerializerMethodField() 
    tags = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()
    total_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'category', 'product_type', 'name', 'slug', 'description',
            'price', 'compare_at_price', 'sku', 'badge', 'video_url', 'video_file', 'weight',
            'is_active', 'created_at',
            'material', 'material_source', 'material_verified', 'special_features', 'care_and_cleaning', 'manufactured_by',
            'tags', 'rating', 'review_count', 'in_stock', 'total_stock',
            'images', 'variants',
        ]

    def _is_owner(self):
        request = self.context.get('request')
        return bool(self.context.get('owner_editor') and request and request.user.is_authenticated and request.user.is_staff)

    def get_material(self, obj):
        return obj.material if self._is_owner() or self.get_material_verified(obj) else ''

    def get_material_source(self, obj):
        return obj.material_source if self._is_owner() else ''

    def get_material_verified(self, obj):
        return bool(obj.material_verified_at and obj.material and obj.material_source)

    def get_tags(self, obj):
        return [
            {'id': tag.id, 'name': tag.name, 'slug': tag.slug}
            for tag in obj.tags.all()
        ]

    def get_rating(self, obj):
        # Use an annotation when the queryset provided one (avoids extra queries).
        for attr in ('_avg_rating', 'avg_rating'):
            value = getattr(obj, attr, None)
            if value is not None:
                return round(float(value), 1)
        reviews = approved_reviews(obj)
        if not reviews:
            return None
        return round(sum(r.rating for r in reviews) / len(reviews), 1)

    def get_review_count(self, obj):
        for attr in ('_review_count', 'review_count'):
            value = getattr(obj, attr, None)
            if value is not None:
                return int(value)
        return len(approved_reviews(obj))

    def get_in_stock(self, obj):
        variants = obj.variants.all()
        return any((v.stock or 0) > 0 for v in variants)

    def get_total_stock(self, obj):
        return sum((v.stock or 0) for v in obj.variants.all())

    def get_video_file(self, obj):
        request = self.context.get('request') 
        url = obj.video_file.url if obj.video_file else None
        if url and request: 
            return request.build_absolute_uri(url) 
        return url




class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ['id', 'user_name', 'rating', 'title', 'body', 'created_at']

    def get_user_name(self, obj):
        return f'{obj.user.first_name} {obj.user.last_name}'.strip() or obj.user.email


class WriteReviewSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    title = serializers.CharField(max_length=150, required=False, allow_blank=True)
    body = serializers.CharField(required=False, allow_blank=True)


class SizeChartSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = SizeChart
        fields = ['id', 'name', 'columns', 'rows', 'note', 'image', 'updated_at']

    def get_image(self, obj):
        request = self.context.get('request')
        url = obj.image.url if obj.image else None
        if url and request:
            return request.build_absolute_uri(url)
        return url
