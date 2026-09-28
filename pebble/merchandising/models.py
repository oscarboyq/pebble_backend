from django.db import models

from products.models import Product


class SmartCollection(models.Model):
    """A rule-based (smart) or hand-picked (manual) collection of products.

    ``sort`` and ``limit`` control how the resolved product list is ordered and
    capped. ``match_mode`` only applies to ``smart`` collections when more than
    one rule is present.
    """

    TYPE_SMART = 'smart'
    TYPE_MANUAL = 'manual'
    TYPE_CHOICES = [
        (TYPE_SMART, 'Smart (rule-based)'),
        (TYPE_MANUAL, 'Manual (hand-picked)'),
    ]

    SORT_NEWEST = 'newest'
    SORT_BEST_SELLING = 'best_selling'
    SORT_PRICE_ASC = 'price_asc'
    SORT_PRICE_DESC = 'price_desc'
    SORT_TOP_RATED = 'top_rated'
    SORT_MANUAL = 'manual'
    SORT_CHOICES = [
        (SORT_NEWEST, 'Newest'),
        (SORT_BEST_SELLING, 'Best selling'),
        (SORT_PRICE_ASC, 'Price: low to high'),
        (SORT_PRICE_DESC, 'Price: high to low'),
        (SORT_TOP_RATED, 'Top rated'),
        (SORT_MANUAL, 'Manual order'),
    ]

    MATCH_ALL = 'all'
    MATCH_ANY = 'any'
    MATCH_CHOICES = [
        (MATCH_ALL, 'Match all rules (AND)'),
        (MATCH_ANY, 'Match any rule (OR)'),
    ]

    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='collections/', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    collection_type = models.CharField(
        max_length=10, choices=TYPE_CHOICES, default=TYPE_SMART
    )
    match_mode = models.CharField(
        max_length=3, choices=MATCH_CHOICES, default=MATCH_ALL
    )
    sort = models.CharField(max_length=20, choices=SORT_CHOICES, default=SORT_NEWEST)
    limit = models.PositiveIntegerField(default=12)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'name']
        indexes = [
            models.Index(fields=['is_active', 'slug']),
        ]

    def __str__(self):
        return self.name


class SmartCollectionRule(models.Model):
    FIELD_CREATED_AT = 'created_at'
    FIELD_PRICE = 'price'
    FIELD_CATEGORY = 'category'
    FIELD_GENDER = 'gender'
    FIELD_IN_STOCK = 'in_stock'
    FIELD_ON_SALE = 'on_sale'
    FIELD_BADGE = 'badge'
    FIELD_TAG = 'tag'
    FIELD_RATING = 'rating'
    FIELD_CHOICES = [
        (FIELD_CREATED_AT, 'Created date'),
        (FIELD_PRICE, 'Price'),
        (FIELD_CATEGORY, 'Category'),
        (FIELD_GENDER, 'Gender'),
        (FIELD_IN_STOCK, 'In stock'),
        (FIELD_ON_SALE, 'On sale'),
        (FIELD_BADGE, 'Badge'),
        (FIELD_TAG, 'Tag'),
        (FIELD_RATING, 'Rating'),
    ]

    OP_EQ = 'eq'
    OP_NEQ = 'neq'
    OP_GT = 'gt'
    OP_GTE = 'gte'
    OP_LT = 'lt'
    OP_LTE = 'lte'
    OP_IN = 'in'
    OP_WITHIN_DAYS = 'within_days'
    OP_CHOICES = [
        (OP_EQ, 'equals'),
        (OP_NEQ, 'not equals'),
        (OP_GT, 'greater than'),
        (OP_GTE, 'greater than or equal'),
        (OP_LT, 'less than'),
        (OP_LTE, 'less than or equal'),
        (OP_IN, 'is one of'),
        (OP_WITHIN_DAYS, 'within last N days'),
    ]

    collection = models.ForeignKey(
        SmartCollection, on_delete=models.CASCADE, related_name='rules'
    )
    order = models.PositiveIntegerField(default=0)
    field = models.CharField(max_length=30, choices=FIELD_CHOICES)
    operator = models.CharField(max_length=20, choices=OP_CHOICES, default=OP_EQ)
    value = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['collection', 'order']),
        ]

    def __str__(self):
        return f'{self.collection.name}: {self.field} {self.operator} {self.value}'


class SmartCollectionPin(models.Model):
    """Products boosted to the front of a collection, in ``position`` order."""

    collection = models.ForeignKey(
        SmartCollection, on_delete=models.CASCADE, related_name='pins'
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'id']
        unique_together = ('collection', 'product')

    def __str__(self):
        return f'{self.collection.name} pin: {self.product.name}'


class SmartCollectionHide(models.Model):
    """Products explicitly excluded from a collection."""

    collection = models.ForeignKey(
        SmartCollection, on_delete=models.CASCADE, related_name='hides'
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('collection', 'product')

    def __str__(self):
        return f'{self.collection.name} hide: {self.product.name}'


class SmartCollectionManualProduct(models.Model):
    """Ordered hand-picked products for ``collection_type == manual``."""

    collection = models.ForeignKey(
        SmartCollection, on_delete=models.CASCADE, related_name='manual_products'
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'id']
        unique_together = ('collection', 'product')

    def __str__(self):
        return f'{self.collection.name} item: {self.product.name}'
