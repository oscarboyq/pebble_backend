from rest_framework .views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.contrib.auth.models import User 
from django.utils import timezone 
from django.utils.text import slugify
from django.db.models import Count, Sum, Q
from django.db import transaction
from datetime import timedelta
import json
from orders.models import Order, OrderItem
from products.models import Product, Category, ProductImage, ProductVariant, CategoryVariantTemplate, CategoryVariantOption, Tag 
from products.serializers import (ProductSerializer, 
                                  CategorySerializer, 
                                  AdminCategorySerializer, 
                                  ProductVariantSerializer,
                                CategoryVariantTemplateSerializer,
                                CategoryVariantOptionSerializer
                                )
from orders.serializers import OrderSerializer, OrderStatusUpdateSerializer
from orders.lifecycle import update_order_status
from home.models import (
    BannerSlide,
    PromoBar,
    StoreSettings,
    MegaMenuSection,
    MegaMenuSectionCategory,
    CollectionsMenuColumn,
    CollectionsMenuLink,
    CollectionsMenuPromo,
    ShopMenuPromo
)
from merchandising.models import (
    SmartCollection,
    SmartCollectionRule,
    SmartCollectionPin,
    SmartCollectionHide,
    SmartCollectionManualProduct,
)
from merchandising.services import engine

def _normalize_tag_specs(data):
    """Extract a list of tag specs from JSON or multipart request data.

    Returns ``None`` when the request does not mention tags (leave unchanged).
    Each spec may be an int/str id, a name string, or ``{id|name|slug}``.
    """
    raw = None
    if hasattr(data, 'getlist'):
        raw = data.getlist('tags')
        if not raw and 'tags' in data:
            raw = data.get('tags')
    else:
        raw = data.get('tags')
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            parsed = [x.strip() for x in raw.split(',') if x.strip()]
        raw = parsed
    if not isinstance(raw, (list, tuple)):
        raw = [raw]
    return list(raw)


def _apply_product_tags(product, data):
    specs = _normalize_tag_specs(data)
    if specs is None:
        return
    tags = []
    for item in specs:
        tid = None
        name = ''
        slug = ''
        if isinstance(item, dict):
            tid = item.get('id')
            name = (item.get('name') or '').strip()
            slug = (item.get('slug') or '').strip()
        else:
            text = str(item).strip()
            if not text:
                continue
            if text.isdigit():
                tid = int(text)
            else:
                name = text
        tag = None
        if tid:
            tag = Tag.objects.filter(pk=tid).first()
        if tag is None and (name or slug):
            slug = slug or slugify(name)
            tag, _ = Tag.objects.get_or_create(
                slug=slug, defaults={'name': name or slug}
            )
        if tag is not None:
            tags.append(tag)
    product.tags.set(tags)


class DashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.now().date()
        this_year  = today.year
        this_month = today.month

        # Last month (handle January → December of previous year)
        if this_month == 1:
            last_year, last_month = this_year - 1, 12
        else:
            last_year, last_month = this_year, this_month - 1

        # ── All-time order counts (for status funnel) ─────────────
        total_orders      = Order.objects.count()
        orders_today      = Order.objects.filter(created_at__date=today).count()
        orders_yesterday  = Order.objects.filter(created_at__date=today - timedelta(days=1)).count()
        pending_orders    = Order.objects.filter(status='pending').count()
        processing_orders = Order.objects.filter(status__in=['confirmed', 'shipped']).count()
        delivered_orders  = Order.objects.filter(status='delivered').count()
        cancelled_orders  = Order.objects.filter(status='cancelled').count()

        # ── This month / last month order counts ──────────────────
        orders_this_month = Order.objects.filter(
            created_at__year=this_year, created_at__month=this_month
        ).count()
        orders_last_month = Order.objects.filter(
            created_at__year=last_year, created_at__month=last_month
        ).count()

        # ── Revenue: delivered orders only ────────────────────────
        delivered_qs = Order.objects.filter(status='delivered')

        total_revenue = delivered_qs.aggregate(
            total=Sum('total_amount')
        )['total'] or 0

        revenue_today = delivered_qs.filter(
            updated_at__date=today
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        revenue_this_month = delivered_qs.filter(
            updated_at__year=this_year, updated_at__month=this_month
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        revenue_last_month = delivered_qs.filter(
            updated_at__year=last_year, updated_at__month=last_month
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        # ── Customers & stock ─────────────────────────────────────
        total_customers = User.objects.filter(is_staff=False).count()
        customers_this_month = User.objects.filter(
            is_staff=False,
            date_joined__year=this_year,
            date_joined__month=this_month
        ).count()
        customers_last_month = User.objects.filter(
            is_staff=False,
            date_joined__year=last_year,
            date_joined__month=last_month
        ).count()
        pending_this_month = Order.objects.filter(
            status='pending',
            created_at__year=this_year,
            created_at__month=this_month
        ).count()
        pending_last_month = Order.objects.filter(
            status='pending',
            created_at__year=last_year,
            created_at__month=last_month
        ).count()
        low_stock_products = Product.objects.filter(
            is_active=True, variants__stock__lte=5
        ).distinct().count()

        # ── Revenue trend: last 7 days (delivered only) ───────────
        revenue_trend = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_revenue = delivered_qs.filter(
                updated_at__date=day
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            revenue_trend.append({'date': str(day), 'revenue': str(day_revenue)})

        # ── Month comparison: day-by-day revenue for current vs last month ──
        # Days 1..today.day for this month, days 1..days_in_last_month for last
        import calendar
        days_in_last = calendar.monthrange(last_year, last_month)[1]
        max_day = max(today.day, days_in_last)
        month_comparison = []
        for d in range(1, max_day + 1):
            # This month: only up to today
            if d <= today.day:
                import datetime as dt_mod
                this_date = dt_mod.date(this_year, this_month, d)
                this_rev = delivered_qs.filter(
                    updated_at__date=this_date
                ).aggregate(t=Sum('total_amount'))['t'] or 0
            else:
                this_rev = None  # future days → null

            # Last month: only up to days_in_last
            if d <= days_in_last:
                import datetime as dt_mod
                last_date = dt_mod.date(last_year, last_month, d)
                last_rev = delivered_qs.filter(
                    updated_at__date=last_date
                ).aggregate(t=Sum('total_amount'))['t'] or 0
            else:
                last_rev = None

            month_comparison.append({
                'day': d,
                'this_month': str(this_rev) if this_rev is not None else None,
                'last_month': str(last_rev) if last_rev is not None else None,
            })

        # ── Recent orders ─────────────────────────────────────────
        recent_orders = Order.objects.select_related('user').order_by('-created_at')[:8]
        recent_orders_data = [
            {
                'id': o.id,
                'customer': f"{o.user.first_name} {o.user.last_name}".strip() or o.user.email,
                'total': str(o.total_amount),
                'status': o.status,
                'created_at': o.created_at,
            }
            for o in recent_orders
        ]

        return Response({
            'total_orders':        total_orders,
            'orders_today':        orders_today,
            'orders_yesterday':    orders_yesterday,
            'orders_this_month':   orders_this_month,
            'orders_last_month':   orders_last_month,
            'revenue_today':       str(revenue_today),
            'total_revenue':       str(total_revenue),
            'revenue_this_month':  str(revenue_this_month),
            'revenue_last_month':  str(revenue_last_month),
            'pending_orders':      pending_orders,
            'processing_orders':   processing_orders,
            'delivered_orders':    delivered_orders,
            'cancelled_orders':    cancelled_orders,
            'total_customers':        total_customers,
            'customers_this_month':   customers_this_month,
            'customers_last_month':   customers_last_month,
            'pending_this_month':     pending_this_month,
            'pending_last_month':     pending_last_month,
            'low_stock_products':     low_stock_products,
            'recent_orders':       recent_orders_data,
            'revenue_trend':       revenue_trend,
            'month_comparison':    month_comparison,
        })


class AdminOrderListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        status_filter = request.query_params.get('status', '').strip()
        orders = Order.objects.select_related('user').prefetch_related('items', 'status_events')
        if status_filter:
            orders = orders.filter(status=status_filter)
        serializer = OrderSerializer(orders, many=True, context={'request': request})
        return Response(serializer.data)
    

class AdminOrderDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        try:
            order = Order.objects.prefetch_related('items', 'status_events').get(pk=pk)
        except Order.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        serializer = OrderSerializer(order, context={'request': request})
        return Response(serializer.data)

    def patch(self, request, pk):
        serializer = OrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = update_order_status(pk, serializer.validated_data, request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        serializer = OrderSerializer(order, context={'request': request})
        return Response(serializer.data)
    

class AdminProductListView(APIView): 
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        products = Product.objects.select_related('category') \
        .prefetch_related('images', 'variants', 'tags', 'reviews') \
        .order_by('-created_at')
        serializer = ProductSerializer(products, many=True, context={'request': request, 'owner_editor': True})
        return Response(serializer.data) 
    
    def post(self, request):
        data = request.data
        product_type = str(data.get('product_type', '')).strip()
        if len(product_type) > 80:
            return Response({'product_type': 'Use 80 characters or fewer.'}, status=400)
        material = str(data.get('material', '')).strip()
        material_source = str(data.get('material_source', '')).strip()
        verify_material = str(data.get('material_verified', 'false')).lower() in ('true', '1', 'yes', 'on')
        if verify_material and (not material or not material_source):
            return Response({'material_verified': 'Material and its evidence are required for verification.'}, status=400)
        try:
            category = Category.objects.get(pk=data['category_id'])
        except (Category.DoesNotExist, KeyError):
            return Response({'category_id': 'Invalid or missing.'}, status=400)

        slug = slugify(data.get('name', ''))
        if not slug:
            return Response({'name': 'Required.'}, status=400)

        # Ensure slug uniqueness
        base, counter = slug, 1
        while Product.objects.filter(slug=slug).exists():
            slug = f'{base}-{counter}'
            counter += 1

        product = Product.objects.create(
            category=category,
            product_type=product_type,
            name=data.get('name', ''),
            slug=slug,
            description=data.get('description', ''),
            price=data.get('price', 0),
            compare_at_price=data.get('compare_at_price') or None,
            sku=data.get('sku', ''),
            badge=data.get('badge', ''),
            is_active=str(data.get('is_active', 'true')).lower() in ['true', '1', 'yes', 'on'],
            video_url=data.get('video_url', ''),
            weight=data.get('weight') or None,
            material=material,
            material_source=material_source,
            material_verified_at=timezone.now() if verify_material else None,
            material_verified_by=request.user if verify_material else None,
            special_features=data.get('special_features', ''),
            care_and_cleaning=data.get('care_and_cleaning', ''),
            manufactured_by=data.get('manufactured_by', ''),
            video_file=request.FILES.get('video_file'),
        )
        _apply_product_tags(product, data)
        serializer = ProductSerializer(product, context={'request': request, 'owner_editor': True})
        return Response(serializer.data, status=201)



class AdminProductDetailView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_product(self, pk):
        try:
            return Product.objects.prefetch_related('images', 'variants').get(pk=pk)
        except Product.DoesNotExist:
            return None

    def get(self, request, pk):
        product = self._get_product(pk)
        if not product:
            return Response({'detail': 'Not found.'}, status=404)
        return Response(ProductSerializer(product, context={'request': request, 'owner_editor': True}).data)

    def patch(self, request, pk):
        product = self._get_product(pk)
        if not product:
            return Response({'detail': 'Not found.'}, status=404)

        data = request.data
        if 'product_type' in data and len(str(data['product_type']).strip()) > 80:
            return Response({'product_type': 'Use 80 characters or fewer.'}, status=400)
        material = str(data.get('material', product.material)).strip()
        material_source = str(data.get('material_source', product.material_source)).strip()
        changed_claim = material != product.material or material_source != product.material_source
        verify_material = str(data.get('material_verified', 'false')).lower() in ('true', '1', 'yes', 'on') if 'material_verified' in data else None
        if verify_material and (not material or not material_source):
            return Response({'material_verified': 'Material and its evidence are required for verification.'}, status=400)
        editable = ['name', 'description', 'price', 'compare_at_price',
                    'sku', 'badge', 'video_url', 'weight',
                    'special_features', 'care_and_cleaning', 'manufactured_by',
                    ]
        for field in editable:
            if field in data:
                setattr(product, field, data[field])
        if 'product_type' in data:
            product.product_type = str(data['product_type']).strip()
        product.material = material
        product.material_source = material_source
        if verify_material is True:
            if changed_claim or not product.material_verified_at:
                product.material_verified_at = timezone.now()
                product.material_verified_by = request.user
        elif verify_material is False or changed_claim:
            product.material_verified_at = None
            product.material_verified_by = None
        
        if 'is_active' in data:
            product.is_active = str(data.get('is_active')).lower() in [
                'true', '1', 'yes', 'on'
            ]
        
        video_file = request.FILES.get('video_file')
        if video_file is not None:
            product.video_file = video_file

        if 'category_id' in data:
            try:
                product.category = Category.objects.get(pk=data['category_id'])
            except Category.DoesNotExist:
                return Response({'category_id': 'Invalid.'}, status=400)

        product.save()
        _apply_product_tags(product, data)
        return Response(ProductSerializer(product, context={'request': request, 'owner_editor': True}).data)

    def delete(self, request, pk):
        product = self._get_product(pk)
        if not product:
            return Response({'detail': 'Not found.'}, status=404)
        from django.db.models.deletion import ProtectedError
        try:
            product.delete()
        except ProtectedError:
            # Product is referenced by order items — soft-delete instead
            product.is_active = False
            product.save(update_fields=['is_active'])
        return Response(status=204)
    

class AdminProductImageView(APIView):
    """Upload an image for a product."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'image': 'Required.'}, status=400)

        with transaction.atomic():
            is_primary = _coerce_bool(request.data.get('is_primary'), not product.images.exists())
            if is_primary:
                product.images.update(is_primary=False)
            try:
                order = int(request.data.get('order', product.images.count()))
            except (TypeError, ValueError):
                return Response({'order': 'Must be an integer.'}, status=400)
            if order < 0:
                return Response({'order': 'Must be non-negative.'}, status=400)
            img = ProductImage.objects.create(
                product=product, images=image_file,
                alt_text=request.data.get('alt_text', ''),
                is_primary=is_primary, order=order,
            )
        return Response({'id': img.id, 'url': img.images.url, 'alt_text': img.alt_text,
                         'is_primary': img.is_primary, 'order': img.order}, status=201)

    @transaction.atomic
    def patch(self, request, pk, image_id):
        img = ProductImage.objects.filter(pk=image_id, product_id=pk).first()
        if img is None:
            return Response({'detail': 'Not found.'}, status=404)
        if 'order' in request.data:
            try:
                order = int(request.data['order'])
            except (TypeError, ValueError):
                return Response({'order': 'Must be an integer.'}, status=400)
            if order < 0:
                return Response({'order': 'Must be non-negative.'}, status=400)
            img.order = order
        if 'alt_text' in request.data:
            img.alt_text = str(request.data['alt_text'])[:255]
        if 'is_primary' in request.data:
            if _coerce_bool(request.data['is_primary']):
                ProductImage.objects.filter(product_id=pk).exclude(pk=img.pk).update(is_primary=False)
                img.is_primary = True
            elif img.is_primary:
                return Response({'is_primary': 'Choose another primary image first.'}, status=400)
        img.save()
        return Response({'id': img.id, 'url': img.images.url, 'alt_text': img.alt_text,
                         'is_primary': img.is_primary, 'order': img.order})

    def delete(self, request, pk, image_id):
        try:
            img = ProductImage.objects.get(pk=image_id, product_id=pk)
        except ProductImage.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        was_primary = img.is_primary
        img.delete()
        if was_primary:
            replacement = ProductImage.objects.filter(product_id=pk).first()
            if replacement:
                replacement.is_primary = True
                replacement.save(update_fields=['is_primary'])
        return Response(status=204)
    


class AdminProductVariantListView(APIView):
    """GET /api/admin/products/<pk>/variants/  — list variants for a product
       POST /api/admin/products/<pk>/variants/ — create a new variant"""
    permission_classes = [IsAdminUser]

    def get(self, request, pk): 
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        
        variants = product.variants.all() 
        serializer = ProductVariantSerializer(variants, many=True)
        return Response(serializer.data) 
    
    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        
        data = request.data
        variant = ProductVariant.objects.create(
            product=product,
            color=data.get('color', ''),
            size=data.get('size', ''),
            stock=data.get('stock', 0),
            price_override=data.get('price_override') or None,
            attributes=data.get('attributes', {}),
        )
        serializer = ProductVariantSerializer(variant)
        return Response(serializer.data, status=201)
    

class AdminProductVariantDetailView(APIView):
    """PATCH /api/admin/products/<pk>/variants/<variant_pk>/ — update a variant
       DELETE /api/admin/products/<pk>/variants/<variant_pk>/ — delete a variant"""
    permission_classes = [IsAdminUser]

    def _get_variant(self, pk, variant_pk):
        try:
            return ProductVariant.objects.get(pk=variant_pk, product_id=pk)
        except ProductVariant.DoesNotExist:
            return None
    
    def patch(self, request, pk, variant_pk):
        variant = self._get_variant(pk, variant_pk)
        if variant is None:
            return Response({'detail': 'Not found.'}, status=404)

        data = request.data
        if 'color' in data:
            variant.color = data['color']
        if 'size' in data:
            variant.size = data['size']
        if 'stock' in data:
            variant.stock = data['stock']
        if 'price_override' in data:
            variant.price_override = data['price_override'] or None
        if 'attributes' in data:
            variant.attributes = data['attributes'] or {}
        variant.save()

        serializer = ProductVariantSerializer(variant)
        return Response(serializer.data)

    def delete(self, request, pk, variant_pk):
        variant = self._get_variant(pk, variant_pk)
        if variant is None:
            return Response({'detail': 'Not found.'}, status=404)
        variant.delete()
        return Response(status=204)
    

        

class AdminCategoryListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        categories = Category.objects.annotate(
            active_count=Count('products', filter=Q(products__is_active=True))
        ).order_by('name')
        serializer = AdminCategorySerializer(categories, many=True, context={'request': request})
        return Response(serializer.data)
    
    def post(self, request):
        name = request.data.get('name', '').strip()
        if not name:
            return Response({'name': 'Required.'}, status=400)
        
        slug = slugify(name)
        base, counter = slug, 1
        while Category.objects.filter(slug=slug).exists():
            slug = f'{base}-{counter}'
            counter += 1

        is_featured_raw = request.data.get('is_featured', False)
        category = Category.objects.create(
            name=name,
            slug=slug,
            is_featured=is_featured_raw in (True, 1, '1', 'true', 'True'),
        )

        image_fields = []
        for field in ('image', 'banner_image'):
            if field in request.FILES:
                setattr(category, field, request.FILES[field])
                image_fields.append(field)
        if image_fields:
            category.save(update_fields=image_fields)

        return Response(AdminCategorySerializer(category, context={'request': request}).data, status=201)
    


class AdminCategoryDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        try:
            category = Category.objects.annotate(
                active_count=Count('products', filter=Q(products__is_active=True))
            ).get(pk=pk)
        except Category.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        return Response(
            AdminCategorySerializer(category, context={'request': request}).data
        )

    def patch(self, request, pk):
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        

        if 'name' in request.data:
            category.name = request.data['name']
        if 'is_featured' in request.data:
            val = request.data['is_featured']
            category.is_featured = val in (True, 1, '1', 'true', 'True')
        for field in ('image', 'banner_image'):
            if field in request.FILES:
                setattr(category, field, request.FILES[field])
        category.save()
        return Response(AdminCategorySerializer(category, context={'request': request}).data)
    

    def delete(self, request, pk):
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        from django.db.models.deletion import ProtectedError
        try:
            category.delete()
        except ProtectedError:
            return Response(
                {'detail': 'Cannot delete category while it still has products.'},
                status=409,
            )
        return Response(status=204)
    


class AdminCategoryVariantTemplateListView(APIView):
    """GET /api/admin/categories/<category_id>/variant-templates/  — list templates
       POST /api/admin/categories/<category_id>/variant-templates/ — create a template"""
    permission_classes = [IsAdminUser]

    def get(self, request, category_id):
        try:
            category = Category.objects.get(pk=category_id)
        except Category.DoesNotExist:
            return Response({'detail': 'Category not found.'}, status=404)

        templates = category.variant_templates.prefetch_related('options').all()
        serializer = CategoryVariantTemplateSerializer(templates, many=True)
        return Response(serializer.data)

    def post(self, request, category_id):
        try:
            category = Category.objects.get(pk=category_id)
        except Category.DoesNotExist:
            return Response({'detail': 'Category not found.'}, status=404)

        name = request.data.get('name', '').strip()
        if not name:
            return Response({'name': 'Required.'}, status=400)

        template = CategoryVariantTemplate.objects.create(
            category=category,
            name=name,
            display_order=request.data.get('display_order', 0),
        )
        serializer = CategoryVariantTemplateSerializer(template)
        return Response(serializer.data, status=201)


class AdminCategoryVariantTemplateDetailView(APIView):
    """PATCH /api/admin/categories/<category_id>/variant-templates/<pk>/
       DELETE /api/admin/categories/<category_id>/variant-templates/<pk>/"""
    permission_classes = [IsAdminUser]

    def _get_template(self, category_id, pk):
        try:
            return CategoryVariantTemplate.objects.get(pk=pk, category_id=category_id)
        except CategoryVariantTemplate.DoesNotExist:
            return None

    def patch(self, request, category_id, pk):
        template = self._get_template(category_id, pk)
        if template is None:
            return Response({'detail': 'Not found.'}, status=404)

        if 'name' in request.data:
            template.name = request.data['name']
        if 'display_order' in request.data:
            template.display_order = request.data['display_order']
        template.save()

        serializer = CategoryVariantTemplateSerializer(template)
        return Response(serializer.data)

    def delete(self, request, category_id, pk):
        template = self._get_template(category_id, pk)
        if template is None:
            return Response({'detail': 'Not found.'}, status=404)
        template.delete()
        return Response(status=204)


class AdminCategoryVariantOptionListView(APIView):
    """GET /api/admin/categories/<category_id>/variant-templates/<template_pk>/options/
       POST /api/admin/categories/<category_id>/variant-templates/<template_pk>/options/"""
    permission_classes = [IsAdminUser]

    def get(self, request, category_id, template_pk):
        try:
            template = CategoryVariantTemplate.objects.get(
                pk=template_pk, category_id=category_id
            )
        except CategoryVariantTemplate.DoesNotExist:
            return Response({'detail': 'Template not found.'}, status=404)

        options = template.options.all()
        serializer = CategoryVariantOptionSerializer(options, many=True)
        return Response(serializer.data)

    def post(self, request, category_id, template_pk):
        try:
            template = CategoryVariantTemplate.objects.get(
                pk=template_pk, category_id=category_id
            )
        except CategoryVariantTemplate.DoesNotExist:
            return Response({'detail': 'Template not found.'}, status=404)

        value = request.data.get('value', '').strip()
        if not value:
            return Response({'value': 'Required.'}, status=400)

        option = CategoryVariantOption.objects.create(
            template=template,
            value=value,
            display_order=request.data.get('display_order', 0),
        )
        serializer = CategoryVariantOptionSerializer(option)
        return Response(serializer.data, status=201)


class AdminCategoryVariantOptionDetailView(APIView):
    """PATCH /api/admin/categories/<category_id>/variant-templates/<template_pk>/options/<pk>/
       DELETE /api/admin/categories/<category_id>/variant-templates/<template_pk>/options/<pk>/"""
    permission_classes = [IsAdminUser]

    def _get_option(self, category_id, template_pk, pk):
        try:
            return CategoryVariantOption.objects.get(
                pk=pk,
                template_id=template_pk,
                template__category_id=category_id,
            )
        except CategoryVariantOption.DoesNotExist:
            return None

    def patch(self, request, category_id, template_pk, pk):
        option = self._get_option(category_id, template_pk, pk)
        if option is None:
            return Response({'detail': 'Not found.'}, status=404)

        if 'value' in request.data:
            option.value = request.data['value']
        if 'display_order' in request.data:
            option.display_order = request.data['display_order']
        option.save()

        serializer = CategoryVariantOptionSerializer(option)
        return Response(serializer.data)

    def delete(self, request, category_id, template_pk, pk):
        option = self._get_option(category_id, template_pk, pk)
        if option is None:
            return Response({'detail': 'Not found.'}, status=404)
        option.delete()
        return Response(status=204)
    


class AdminBannerListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        banners = BannerSlide.objects.all()
        data = [
            {
                'id': b.id,
                'title': b.title,
                'subtitle': b.subtitle,
                'image': request.build_absolute_uri(b.image.url) if b.image else None,
                'cta_text': b.cta_text,
                'cta_link': b.cta_link,
                'bg_color': b.bg_color,
                'order': b.order,
                'is_active': b.is_active,
            }
            for b in banners
        ]
        return Response(data)

    def post(self, request):
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'image': 'Required.'}, status=400)

        banner = BannerSlide.objects.create(
            title=request.data.get('title', ''),
            subtitle=request.data.get('subtitle', ''),
            image=image_file,
            cta_text=request.data.get('cta_text', ''),
            cta_link=request.data.get('cta_link', ''),
            bg_color=request.data.get('bg_color', '#C99484'),
            order=request.data.get('order', 0),
            is_active=request.data.get('is_active', True),
        )
        return Response({'id': banner.id, 'title': banner.title}, status=201)
    

class AdminBannerDetailView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        try:
            banner = BannerSlide.objects.get(pk=pk)
        except BannerSlide.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        for field in ['title', 'subtitle', 'cta_text', 'cta_link', 'bg_color', 'order', 'is_active']:
            if field in request.data:
                setattr(banner, field, request.data[field])
        if 'image' in request.FILES:
            banner.image = request.FILES['image']
        banner.save()
        return Response({'id': banner.id, 'title': banner.title})

    def delete(self, request, pk):
        try:
            banner = BannerSlide.objects.get(pk=pk)
        except BannerSlide.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        banner.delete()
        return Response(status=204)


def serialize_mega_menu_section(section, request):
    category_items = section.category_items.select_related('category').all()

    return {
        'id': section.id,
        'key': section.key,
        'title': section.title,
        'is_active': section.is_active,
        'use_manual_categories': section.use_manual_categories,
        'display_mode': section.display_mode,
        'smart_collection': (
            {
                'id': section.smart_collection.id,
                'name': section.smart_collection.name,
                'slug': section.smart_collection.slug,
            }
            if section.smart_collection_id else None
        ),
        'categories': [
            {
                'id': item.category.id,
                'name': item.category.name,
                'slug': item.category.slug,
                'image': request.build_absolute_uri(item.image_override.url)
                if item.image_override else request.build_absolute_uri(item.category.image.url)
                if item.category.image else None,
                'image_override': request.build_absolute_uri(item.image_override.url)
                if item.image_override else None,
                'order': item.order,
            }
            for item in category_items
        ],
    }


class AdminMegaMenuSectionListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        sections = MegaMenuSection.objects.prefetch_related(
            'category_items__category'
        ).order_by('key')

        return Response([
            serialize_mega_menu_section(section, request)
            for section in sections
        ])

    def post(self, request):
        key = request.data.get('key', '').strip()
        title = request.data.get('title', '').strip()

        if not key:
            return Response({'key': 'Required.'}, status=400)

        if not title:
            return Response({'title': 'Required.'}, status=400)

        valid_keys = [
            choice[0]
            for choice in MegaMenuSection.SECTION_CHOICES
        ]

        if key not in valid_keys:
            return Response({'key': 'Invalid mega menu section key.'}, status=400)

        smart_collection = None
        smart_collection_raw = request.data.get('smart_collection')
        if smart_collection_raw not in (None, '', 0, '0', 'null'):
            try:
                smart_collection = SmartCollection.objects.get(
                    pk=int(smart_collection_raw)
                )
            except (SmartCollection.DoesNotExist, ValueError, TypeError):
                return Response(
                    {'smart_collection': 'Invalid collection id.'}, status=400
                )

        section, created = MegaMenuSection.objects.get_or_create(
            key=key,
            defaults={
                'title': title,
                'is_active': request.data.get('is_active', True),
                'use_manual_categories': request.data.get(
                    'use_manual_categories',
                    False,
                ),
                'display_mode': request.data.get(
                    'display_mode', MegaMenuSection.DISPLAY_CATEGORIES
                ),
                'smart_collection': smart_collection,
            },
        )

        if not created:
            return Response(
                {'detail': 'Section with this key already exists.'},
                status=400,
            )

        return Response(
            serialize_mega_menu_section(section, request),
            status=201,
        )


class AdminMegaMenuSectionDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get_section(self, pk):
        try:
            return MegaMenuSection.objects.prefetch_related(
                'category_items__category'
            ).select_related('smart_collection').get(pk=pk)
        except MegaMenuSection.DoesNotExist:
            return None

    def get(self, request, pk):
        section = self.get_section(pk)

        if section is None:
            return Response({'detail': 'Not found.'}, status=404)

        return Response(serialize_mega_menu_section(section, request))

    def patch(self, request, pk):
        section = self.get_section(pk)

        if section is None:
            return Response({'detail': 'Not found.'}, status=404)

        if 'title' in request.data:
            section.title = request.data['title']

        if 'is_active' in request.data:
            val = request.data['is_active']
            section.is_active = val in (True, 1, '1', 'true', 'True')

        if 'use_manual_categories' in request.data:
            val = request.data['use_manual_categories']
            section.use_manual_categories = val in (
                True,
                1,
                '1',
                'true',
                'True',
            )

        if 'display_mode' in request.data:
            value = request.data['display_mode']
            valid_modes = [choice[0] for choice in MegaMenuSection.DISPLAY_CHOICES]
            if value not in valid_modes:
                return Response(
                    {'display_mode': 'Invalid display mode.'}, status=400
                )
            section.display_mode = value

        if 'smart_collection' in request.data:
            value = request.data['smart_collection']
            if value in (None, '', 0, '0', 'null'):
                section.smart_collection = None
            else:
                try:
                    section.smart_collection = SmartCollection.objects.get(
                        pk=int(value)
                    )
                except (SmartCollection.DoesNotExist, ValueError, TypeError):
                    return Response(
                        {'smart_collection': 'Invalid collection id.'},
                        status=400,
                    )

        section.save()

        return Response(serialize_mega_menu_section(section, request))

    def delete(self, request, pk):
        section = self.get_section(pk)

        if section is None:
            return Response({'detail': 'Not found.'}, status=404)

        section.delete()
        return Response(status=204)


class AdminMegaMenuSectionCategoriesView(APIView):
    permission_classes = [IsAdminUser]

    def put(self, request, pk):
        try:
            section = MegaMenuSection.objects.get(pk=pk)
        except MegaMenuSection.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        category_ids = request.data.get('category_ids', [])

        if not isinstance(category_ids, list):
            return Response({'category_ids': 'Must be a list.'}, status=400)

        categories = Category.objects.filter(id__in=category_ids)
        categories_by_id = {
            category.id: category
            for category in categories
        }

        missing_ids = [
            category_id
            for category_id in category_ids
            if category_id not in categories_by_id
        ]

        if missing_ids:
            return Response(
                {'category_ids': f'Invalid category ids: {missing_ids}'},
                status=400,
            )

        if len(set(category_ids)) != len(category_ids):
            return Response({'category_ids': 'Duplicate categories are not allowed.'}, status=400)

        with transaction.atomic():
            section.category_items.exclude(category_id__in=category_ids).delete()
            for index, category_id in enumerate(category_ids):
                MegaMenuSectionCategory.objects.update_or_create(
                    section=section,
                    category=categories_by_id[category_id],
                    defaults={'order': index},
                )
            section.use_manual_categories = True
            section.display_mode = 'categories'
            section.save(update_fields=['use_manual_categories', 'display_mode'])

        section = MegaMenuSection.objects.prefetch_related(
            'category_items__category'
        ).get(pk=section.pk)

        return Response(serialize_mega_menu_section(section, request))


class AdminMegaMenuSectionCategoryImageView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request, pk, category_id):
        item = MegaMenuSectionCategory.objects.filter(
            section_id=pk, category_id=category_id,
        ).first()
        if item is None:
            return Response({'detail': 'Menu category not found.'}, status=404)
        if 'image' in request.FILES:
            item.image_override = request.FILES['image']
        elif str(request.data.get('clear_image', 'false')).lower() in ('true', '1'):
            item.image_override = None
        else:
            return Response({'image': 'Upload an image or clear the override.'}, status=400)
        item.save(update_fields=['image_override'])
        section = MegaMenuSection.objects.prefetch_related('category_items__category').get(pk=pk)
        return Response(serialize_mega_menu_section(section, request))
    

def serialize_collections_menu_column(column):
    return {
        'id': column.id,
        'title': column.title,
        'order': column.order,
        'is_active': column.is_active,
        'links': [
            {
                'id': link.id,
                'label': link.label,
                'route': link.route,
                'order': link.order,
                'is_active': link.is_active,
            }
            for link in column.links.all()
        ],
    }


class AdminCollectionsMenuColumnListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        columns = CollectionsMenuColumn.objects.prefetch_related(
            'links'
        ).all()

        return Response([
            serialize_collections_menu_column(column)
            for column in columns
        ])

    def post(self, request):
        title = request.data.get('title', '').strip()

        if not title:
            return Response({'title': 'Required.'}, status=400)

        column = CollectionsMenuColumn.objects.create(
            title=title,
            order=request.data.get('order', 0),
            is_active=request.data.get('is_active', True),
        )

        return Response(serialize_collections_menu_column(column), status=201)


class AdminCollectionsMenuColumnDetailView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        try:
            column = CollectionsMenuColumn.objects.get(pk=pk)
        except CollectionsMenuColumn.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        if 'title' in request.data:
            column.title = request.data['title']

        if 'order' in request.data:
            column.order = request.data['order']

        if 'is_active' in request.data:
            val = request.data['is_active']
            column.is_active = val in (True, 1, '1', 'true', 'True')

        column.save()
        return Response(serialize_collections_menu_column(column))

    def delete(self, request, pk):
        try:
            column = CollectionsMenuColumn.objects.get(pk=pk)
        except CollectionsMenuColumn.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        column.delete()
        return Response(status=204)


class AdminCollectionsMenuLinkListView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, column_id):
        try:
            column = CollectionsMenuColumn.objects.get(pk=column_id)
        except CollectionsMenuColumn.DoesNotExist:
            return Response({'detail': 'Column not found.'}, status=404)

        label = request.data.get('label', '').strip()
        route = request.data.get('route', '').strip()

        if not label:
            return Response({'label': 'Required.'}, status=400)

        if not route:
            return Response({'route': 'Required.'}, status=400)

        link = CollectionsMenuLink.objects.create(
            column=column,
            label=label,
            route=route,
            order=request.data.get('order', 0),
            is_active=request.data.get('is_active', True),
        )

        return Response({
            'id': link.id,
            'label': link.label,
            'route': link.route,
            'order': link.order,
            'is_active': link.is_active,
        }, status=201)


class AdminCollectionsMenuLinkDetailView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        try:
            link = CollectionsMenuLink.objects.get(pk=pk)
        except CollectionsMenuLink.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        for field in ['label', 'route', 'order']:
            if field in request.data:
                setattr(link, field, request.data[field])

        if 'is_active' in request.data:
            val = request.data['is_active']
            link.is_active = val in (True, 1, '1', 'true', 'True')

        link.save()

        return Response({
            'id': link.id,
            'label': link.label,
            'route': link.route,
            'order': link.order,
            'is_active': link.is_active,
        })

    def delete(self, request, pk):
        try:
            link = CollectionsMenuLink.objects.get(pk=pk)
        except CollectionsMenuLink.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        link.delete()
        return Response(status=204)
    

class AdminCollectionsMenuPromoListView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        promos = CollectionsMenuPromo.objects.all()

        return Response([
            {
                'id': promo.id,
                'title': promo.title,
                'image': request.build_absolute_uri(promo.image.url)
                if promo.image else None,
                'route': promo.route,
                'order': promo.order,
                'is_active': promo.is_active,
            }
            for promo in promos
        ])

    def post(self, request):
        image = request.FILES.get('image')
        title = request.data.get('title', '').strip()
        route = request.data.get('route', '').strip()

        if not title:
            return Response({'title': 'Required.'}, status=400)

        if not route:
            return Response({'route': 'Required.'}, status=400)

        if not image:
            return Response({'image': 'Required.'}, status=400)

        promo = CollectionsMenuPromo.objects.create(
            title=title,
            image=image,
            route=route,
            order=request.data.get('order', 0),
            is_active=request.data.get('is_active', True),
        )

        return Response({'id': promo.id, 'title': promo.title}, status=201)


class AdminCollectionsMenuPromoDetailView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request, pk):
        try:
            promo = CollectionsMenuPromo.objects.get(pk=pk)
        except CollectionsMenuPromo.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        for field in ['title', 'route', 'order']:
            if field in request.data:
                setattr(promo, field, request.data[field])

        if 'is_active' in request.data:
            val = request.data['is_active']
            promo.is_active = val in (True, 1, '1', 'true', 'True')

        if 'image' in request.FILES:
            promo.image = request.FILES['image']

        promo.save()

        return Response({'id': promo.id, 'title': promo.title})

    def delete(self, request, pk):
        try:
            promo = CollectionsMenuPromo.objects.get(pk=pk)
        except CollectionsMenuPromo.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        promo.delete()
        return Response(status=204)


class AdminShopMenuPromoListView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        promos = ShopMenuPromo.objects.all().order_by('id')
        return Response([
            {
                'id': promo.id,
                'section': promo.section,
                'section_display': promo.get_section_display(),
                'eyebrow': promo.eyebrow,
                'title': promo.title,
                'cta_text': promo.cta_text,
                'cta_link': promo.cta_link,
                'image': request.build_absolute_uri(promo.image.url) if promo.image else None,
                'bg_color': promo.bg_color,
                'is_active': promo.is_active,
            }
            for promo in promos
        ])

    def post(self, request):
        section = request.data.get('section', '').strip()
        if not section:
            return Response({'section': 'Required.'}, status=400)

        eyebrow = request.data.get('eyebrow', 'NEW COLLECTION').strip()
        title = request.data.get('title', '').strip()
        cta_text = request.data.get('cta_text', 'Shop Now').strip()
        cta_link = request.data.get('cta_link', '/products').strip()
        bg_color = request.data.get('bg_color', '#84A999').strip()
        is_active = request.data.get('is_active', True)
        if isinstance(is_active, str):
            is_active = is_active.lower() in ('true', '1')

        promo, created = ShopMenuPromo.objects.update_or_create(
            section=section,
            defaults={
                'eyebrow': eyebrow,
                'title': title,
                'cta_text': cta_text,
                'cta_link': cta_link,
                'bg_color': bg_color,
                'is_active': is_active,
            }
        )

        if 'image' in request.FILES:
            promo.image = request.FILES['image']
            promo.save()

        return Response({
            'id': promo.id,
            'section': promo.section,
            'title': promo.title,
            'image': request.build_absolute_uri(promo.image.url) if promo.image else None,
        }, status=201 if created else 200)


class AdminShopMenuPromoDetailView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, pk):
        try:
            promo = ShopMenuPromo.objects.get(pk=pk)
        except ShopMenuPromo.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        return Response({
            'id': promo.id,
            'section': promo.section,
            'section_display': promo.get_section_display(),
            'eyebrow': promo.eyebrow,
            'title': promo.title,
            'cta_text': promo.cta_text,
            'cta_link': promo.cta_link,
            'image': request.build_absolute_uri(promo.image.url) if promo.image else None,
            'bg_color': promo.bg_color,
            'is_active': promo.is_active,
        })

    def patch(self, request, pk):
        try:
            promo = ShopMenuPromo.objects.get(pk=pk)
        except ShopMenuPromo.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        for field in ['section', 'eyebrow', 'title', 'cta_text', 'cta_link', 'bg_color']:
            if field in request.data:
                setattr(promo, field, request.data[field])

        if 'is_active' in request.data:
            val = request.data['is_active']
            promo.is_active = val in (True, 1, '1', 'true', 'True')

        if 'image' in request.FILES:
            promo.image = request.FILES['image']

        promo.save()

        return Response({
            'id': promo.id,
            'section': promo.section,
            'section_display': promo.get_section_display(),
            'eyebrow': promo.eyebrow,
            'title': promo.title,
            'cta_text': promo.cta_text,
            'cta_link': promo.cta_link,
            'image': request.build_absolute_uri(promo.image.url) if promo.image else None,
            'bg_color': promo.bg_color,
            'is_active': promo.is_active,
        })

    def delete(self, request, pk):
        try:
            promo = ShopMenuPromo.objects.get(pk=pk)
        except ShopMenuPromo.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        promo.delete()
        return Response(status=204)





# ─────────────────────────────────────────────────────────────────────────────
# Monthly Orders Summary  GET /api/admin/orders/monthly-summary/
# Returns one entry per calendar month from first order to today, newest first.
# ─────────────────────────────────────────────────────────────────────────────
class AdminMonthlySummaryView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        import calendar
        import datetime as dt_mod

        today = timezone.now().date()

        # Find the first ever order date
        first_order = Order.objects.order_by('created_at').first()
        if first_order is None:
            return Response([])

        start = first_order.created_at.date().replace(day=1)
        current = today.replace(day=1)

        months = []
        ptr = current
        while ptr >= start:
            year  = ptr.year
            month = ptr.month
            days_in = calendar.monthrange(year, month)[1]
            month_start = dt_mod.date(year, month, 1)
            month_end   = dt_mod.date(year, month, days_in)

            qs = Order.objects.filter(
                created_at__date__gte=month_start,
                created_at__date__lte=month_end,
            )

            total_orders = qs.count()
            revenue = qs.filter(status='delivered').aggregate(
                t=Sum('total_amount')
            )['t'] or 0
            delivered  = qs.filter(status='delivered').count()
            cancelled  = qs.filter(status='cancelled').count()
            pending    = qs.filter(status='pending').count()
            processing = qs.filter(status__in=['confirmed', 'shipped']).count()

            months.append({
                'year':         year,
                'month':        month,
                'month_label':  dt_mod.date(year, month, 1).strftime('%B %Y'),
                'total_orders': total_orders,
                'revenue':      str(revenue),
                'delivered':    delivered,
                'cancelled':    cancelled,
                'pending':      pending,
                'processing':   processing,
            })

            # Move to previous month
            if month == 1:
                ptr = dt_mod.date(year - 1, 12, 1)
            else:
                ptr = dt_mod.date(year, month - 1, 1)

        return Response(months)


# ─────────────────────────────────────────────────────────────────────────────
# Admin Reviews   GET /api/admin/reviews/
#                 PATCH /api/admin/reviews/<pk>/
#                 DELETE /api/admin/reviews/<pk>/
# ─────────────────────────────────────────────────────────────────────────────
from products.models import Review

class AdminReviewListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        reviews = Review.objects.select_related('user', 'product').order_by('-created_at')
        data = [
            {
                'id': r.id,
                'user_name': f'{r.user.first_name} {r.user.last_name}'.strip() or r.user.email,
                'product_name': r.product.name,
                'rating': r.rating,
                'title': r.title,
                'body': r.body,
                'is_approved': r.is_approved,
                'created_at': r.created_at,
            }
            for r in reviews
        ]
        return Response(data)


class AdminReviewDetailView(APIView):
    permission_classes = [IsAdminUser]

    def _get(self, pk):
        try:
            return Review.objects.select_related('user', 'product').get(pk=pk)
        except Review.DoesNotExist:
            return None

    def patch(self, request, pk):
        review = self._get(pk)
        if review is None:
            return Response({'detail': 'Not found.'}, status=404)
        if 'is_approved' in request.data:
            review.is_approved = bool(request.data['is_approved'])
            review.save(update_fields=['is_approved'])
        return Response({
            'id': review.id,
            'user_name': f'{review.user.first_name} {review.user.last_name}'.strip() or review.user.email,
            'product_name': review.product.name,
            'rating': review.rating,
            'title': review.title,
            'body': review.body,
            'is_approved': review.is_approved,
            'created_at': review.created_at,
        })

    def delete(self, request, pk):
        review = self._get(pk)
        if review is None:
            return Response({'detail': 'Not found.'}, status=404)
        review.delete()
        return Response(status=204)


class AdminCustomerListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        users = (
            User.objects
            .annotate(order_count=Count('orders'))
            .order_by('-date_joined')
        )
        data = [
            {
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'first_name': u.first_name,
                'last_name': u.last_name,
                'is_active': u.is_active,
                'date_joined': u.date_joined,
                'order_count': u.order_count,
            }
            for u in users
        ]
        return Response(data)


class AdminCustomerDetailView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        if 'is_active' in request.data:
            user.is_active = bool(request.data['is_active'])
            user.save(update_fields=['is_active'])
        order_count = user.orders.count()
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'date_joined': user.date_joined,
            'order_count': order_count,
        })


from coupons.models import Coupon


def _coupon_data(c):
    return {
        'id': c.id,
        'code': c.code,
        'discount_type': c.discount_type,
        'discount_value': str(c.discount_value),
        'min_order_amount': str(c.min_order_amount) if c.min_order_amount is not None else None,
        'usage_limit': c.usage_limit,
        'usage_count': c.usage_count,
        'is_active': c.is_active,
        'expires_at': c.expires_at.isoformat() if c.expires_at else None,
    }


class AdminCouponListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        coupons = Coupon.objects.all().order_by('-created_at')
        return Response([_coupon_data(c) for c in coupons])

    def post(self, request):
        d = request.data
        coupon = Coupon.objects.create(
            code=str(d.get('code', '')).upper(),
            discount_type=d.get('discount_type', 'percent'),
            discount_value=d.get('discount_value', 0),
            min_order_amount=d.get('min_order_amount') or None,
            usage_limit=d.get('usage_limit') or None,
            is_active=d.get('is_active', True),
            expires_at=d.get('expires_at') or None,
        )
        return Response(_coupon_data(coupon), status=201)


class AdminCouponDetailView(APIView):
    permission_classes = [IsAdminUser]

    def _get(self, pk):
        try:
            return Coupon.objects.get(pk=pk)
        except Coupon.DoesNotExist:
            return None

    def patch(self, request, pk):
        coupon = self._get(pk)
        if coupon is None:
            return Response({'detail': 'Not found.'}, status=404)
        d = request.data
        if 'code' in d:
            coupon.code = str(d['code']).upper()
        if 'discount_type' in d:
            coupon.discount_type = d['discount_type']
        if 'discount_value' in d:
            coupon.discount_value = d['discount_value']
        if 'min_order_amount' in d:
            coupon.min_order_amount = d['min_order_amount'] or None
        if 'usage_limit' in d:
            coupon.usage_limit = d['usage_limit'] or None
        if 'is_active' in d:
            coupon.is_active = bool(d['is_active'])
        if 'expires_at' in d:
            coupon.expires_at = d['expires_at'] or None
        coupon.save()
        return Response(_coupon_data(coupon))

    def delete(self, request, pk):
        coupon = self._get(pk)
        if coupon is None:
            return Response({'detail': 'Not found.'}, status=404)
        coupon.delete()
        return Response(status=204)


class AdminSettingsView(APIView):
    permission_classes = [IsAdminUser]

    def _instance(self):
        obj, _ = StoreSettings.objects.get_or_create(pk=1)
        return obj

    def _serialize(self, s, request):
        logo_url = None
        if s.logo:
            logo_url = request.build_absolute_uri(s.logo.url)
        return {
            'store_name': s.store_name,
            'logo': logo_url,
            'contact_email': s.contact_email,
            'promo_bar_text': s.promo_bar_text,
            'promo_bar_enabled': s.promo_bar_enabled,
            'hero_transition': s.hero_transition,
        }

    def get(self, request):
        return Response(self._serialize(self._instance(), request))

    def patch(self, request, *args, **kwargs):
        s = self._instance()
        d = request.data
        if 'store_name' in d:
            s.store_name = d['store_name']
        if 'contact_email' in d:
            s.contact_email = d['contact_email']
        if 'promo_bar_text' in d:
            s.promo_bar_text = d['promo_bar_text']
        if 'promo_bar_enabled' in d:
            val = d['promo_bar_enabled']
            s.promo_bar_enabled = val if isinstance(val, bool) else str(val).lower() == 'true'
        if 'hero_transition' in d:
            s.hero_transition = d['hero_transition']
        if 'logo' in request.FILES:
            s.logo = request.FILES['logo']
        s.save()
        return Response(self._serialize(s, request))


class AdminInventoryView(APIView):
    """GET  admin/inventory/  — all products with all variants + stock levels."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        low_threshold = int(request.query_params.get('low_threshold', 5))
        products = (
            Product.objects
            .prefetch_related('variants', 'images')
            .filter(is_active=True)
            .order_by('name')
        )
        data = []
        for p in products:
            variants = p.variants.all()
            total_stock = sum(v.stock for v in variants)
            low_count = sum(1 for v in variants if v.stock <= low_threshold)
            # primary image
            imgs = list(p.images.all())
            primary = next((i for i in imgs if i.is_primary), imgs[0] if imgs else None)
            image_url = request.build_absolute_uri(primary.images.url) if primary and primary.images else None
            data.append({
                'id': p.id,
                'name': p.name,
                'sku': p.sku,
                'image': image_url,
                'total_stock': total_stock,
                'variant_count': variants.count(),
                'low_stock_count': low_count,
                'variants': [
                    {
                        'id': v.id,
                        'color': v.color,
                        'size': v.size,
                        'stock': v.stock,
                        'price_override': str(v.price_override) if v.price_override else None,
                    }
                    for v in variants
                ],
            })
        return Response(data)


class AdminInventoryVariantView(APIView):
    """PATCH admin/inventory/variants/<pk>/  — update stock for one variant."""
    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        try:
            variant = ProductVariant.objects.select_related('product').get(pk=pk)
        except ProductVariant.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        new_stock = request.data.get('stock')
        if new_stock is None:
            return Response({'detail': '`stock` field required.'}, status=400)
        try:
            new_stock = int(new_stock)
            if new_stock < 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response({'detail': '`stock` must be a non-negative integer.'}, status=400)

        variant.stock = new_stock
        variant.save(update_fields=['stock'])
        return Response({
            'id': variant.id,
            'product_id': variant.product.id,
            'color': variant.color,
            'size': variant.size,
            'stock': variant.stock,
        })


# ── Smart Collections (admin) ────────────────────────────────────────────────

def _coerce_bool(value, default=False):
    if value is None:
        return default
    return value in (True, 1, '1', 'true', 'True')


def _unique_collection_slug(name, exclude_pk=None):
    base = slugify(name) or 'collection'
    slug = base
    counter = 1
    queryset = SmartCollection.objects.all()
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    while queryset.filter(slug=slug).exists():
        slug = f'{base}-{counter}'
        counter += 1
    return slug


def _collection_payload(collection, request):
    return {
        'id': collection.id,
        'name': collection.name,
        'slug': collection.slug,
        'description': collection.description,
        'image': request.build_absolute_uri(collection.image.url) if collection.image else None,
        'is_featured': collection.is_featured,
        'position': collection.position,
        'is_active': collection.is_active,
        'collection_type': collection.collection_type,
        'match_mode': collection.match_mode,
        'sort': collection.sort,
        'limit': collection.limit,
        'rules': [
            {
                'id': rule.id,
                'order': rule.order,
                'field': rule.field,
                'operator': rule.operator,
                'value': rule.value,
            }
            for rule in collection.rules.all()
        ],
        'pinned_product_ids': list(
            collection.pins.values_list('product_id', flat=True)
        ),
        'hidden_product_ids': list(
            collection.hides.values_list('product_id', flat=True)
        ),
        'manual_product_ids': [
            mp.product_id for mp in collection.manual_products.all()
        ],
        'created_at': collection.created_at,
        'updated_at': collection.updated_at,
    }


class AdminCollectionListView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        collections = SmartCollection.objects.prefetch_related('rules').all()
        return Response([
            _collection_payload(collection, request)
            for collection in collections
        ])

    def post(self, request):
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'name': 'Required.'}, status=400)

        collection = SmartCollection.objects.create(
            name=name,
            slug=_unique_collection_slug(name),
            description=request.data.get('description', ''),
            image=request.FILES.get('image'),
            is_featured=_coerce_bool(request.data.get('is_featured'), False),
            is_active=_coerce_bool(request.data.get('is_active'), True),
            collection_type=request.data.get(
                'collection_type', SmartCollection.TYPE_SMART
            ),
            match_mode=request.data.get('match_mode', SmartCollection.MATCH_ALL),
            sort=request.data.get('sort', SmartCollection.SORT_NEWEST),
            limit=max(1, int(request.data.get('limit', 12) or 12)),
        )
        return Response(_collection_payload(collection, request), status=201)


class AdminCollectionDetailView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_collection(self, pk):
        return SmartCollection.objects.filter(pk=pk).first()

    def get(self, request, pk):
        collection = self.get_collection(pk)
        if collection is None:
            return Response({'detail': 'Not found.'}, status=404)
        return Response(_collection_payload(collection, request))

    def patch(self, request, pk):
        collection = self.get_collection(pk)
        if collection is None:
            return Response({'detail': 'Not found.'}, status=404)

        if 'name' in request.data:
            collection.name = request.data['name']
        if 'description' in request.data:
            collection.description = request.data['description']
        if 'image' in request.FILES:
            collection.image = request.FILES['image']
        if 'is_featured' in request.data:
            collection.is_featured = _coerce_bool(request.data['is_featured'])
        if 'is_active' in request.data:
            collection.is_active = _coerce_bool(request.data['is_active'])
        if 'collection_type' in request.data:
            collection.collection_type = request.data['collection_type']
        if 'match_mode' in request.data:
            collection.match_mode = request.data['match_mode']
        if 'sort' in request.data:
            collection.sort = request.data['sort']
        if 'limit' in request.data:
            try:
                collection.limit = max(1, int(request.data['limit']))
            except (TypeError, ValueError):
                return Response({'limit': 'Must be an integer.'}, status=400)

        collection.save()
        return Response(_collection_payload(collection, request))

    def delete(self, request, pk):
        collection = self.get_collection(pk)
        if collection is None:
            return Response({'detail': 'Not found.'}, status=404)
        collection.delete()
        return Response(status=204)


class AdminCollectionRulesView(APIView):
    permission_classes = [IsAdminUser]

    def put(self, request, pk):
        collection = SmartCollection.objects.filter(pk=pk).first()
        if collection is None:
            return Response({'detail': 'Not found.'}, status=404)

        rules = request.data.get('rules')
        if not isinstance(rules, list):
            return Response({'rules': 'Must be a list.'}, status=400)

        valid_fields = {choice[0] for choice in SmartCollectionRule.FIELD_CHOICES}
        valid_ops = {choice[0] for choice in SmartCollectionRule.OP_CHOICES}

        cleaned = []
        for index, rule in enumerate(rules):
            field = rule.get('field')
            operator = rule.get('operator', 'eq')
            if field not in valid_fields:
                return Response(
                    {'rules': f'Invalid field at index {index}: {field}'},
                    status=400,
                )
            if operator not in valid_ops:
                return Response(
                    {'rules': f'Invalid operator at index {index}: {operator}'},
                    status=400,
                )
            cleaned.append((field, operator, rule.get('value'), index))

        collection.rules.all().delete()
        for field, operator, value, index in cleaned:
            SmartCollectionRule.objects.create(
                collection=collection,
                field=field,
                operator=operator,
                value=value if value is not None else {},
                order=index,
            )

        return Response(_collection_payload(collection, request))


class AdminCollectionProductsView(APIView):
    """Replace pins / hides / manual products in a single call."""

    permission_classes = [IsAdminUser]

    def put(self, request, pk):
        collection = SmartCollection.objects.filter(pk=pk).first()
        if collection is None:
            return Response({'detail': 'Not found.'}, status=404)

        def lookup_ids(key):
            ids = request.data.get(key)
            if ids is None:
                return None
            if not isinstance(ids, list):
                raise ValueError(f'{key} must be a list.')
            ids = [int(i) for i in ids]
            found = set(
                Product.objects.filter(id__in=ids).values_list('id', flat=True)
            )
            invalid = [i for i in ids if i not in found]
            if invalid:
                raise ValueError(f'Invalid product ids for {key}: {invalid}')
            return ids

        try:
            pinned = lookup_ids('pinned_product_ids')
            hidden = lookup_ids('hidden_product_ids')
            manual = lookup_ids('manual_product_ids')
        except (ValueError, TypeError) as exc:
            return Response({'detail': str(exc)}, status=400)

        if pinned is not None:
            SmartCollectionPin.objects.filter(collection=collection).delete()
            for index, product_id in enumerate(pinned):
                SmartCollectionPin.objects.create(
                    collection=collection, product_id=product_id, position=index
                )
        if hidden is not None:
            SmartCollectionHide.objects.filter(collection=collection).delete()
            for product_id in hidden:
                SmartCollectionHide.objects.create(
                    collection=collection, product_id=product_id
                )
        if manual is not None:
            SmartCollectionManualProduct.objects.filter(
                collection=collection
            ).delete()
            for index, product_id in enumerate(manual):
                SmartCollectionManualProduct.objects.create(
                    collection=collection, product_id=product_id, position=index
                )

        return Response(_collection_payload(collection, request))


class AdminCollectionPreviewView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        collection_id = request.data.get('collection_id')

        if collection_id:
            collection = SmartCollection.objects.filter(pk=collection_id).first()
            if collection is None:
                return Response({'detail': 'Not found.'}, status=404)
            rules = [
                {
                    'field': rule.field,
                    'operator': rule.operator,
                    'value': rule.value,
                }
                for rule in collection.rules.all()
            ]
            manual_ids = [mp.product_id for mp in collection.manual_products.all()]
            pinned_ids = list(collection.pins.values_list('product_id', flat=True))
            hidden_ids = list(collection.hides.values_list('product_id', flat=True))
            match_mode = collection.match_mode
            sort = collection.sort
            limit = collection.limit
            collection_type = collection.collection_type
        else:
            rules = request.data.get('rules') or []
            manual_ids = request.data.get('manual_product_ids') or None
            pinned_ids = request.data.get('pinned_product_ids') or None
            hidden_ids = request.data.get('hidden_product_ids') or None
            match_mode = request.data.get('match_mode', 'all')
            sort = request.data.get('sort', 'newest')
            limit = max(1, int(request.data.get('limit', 12) or 12))
            collection_type = request.data.get('collection_type', 'smart')

        if collection_type == 'manual':
            rules = []

        preview_limit = min(limit, 24)
        total, products = engine.preview(
            rules,
            match_mode=match_mode,
            sort=sort,
            limit=preview_limit,
            manual_product_ids=manual_ids,
            pinned_product_ids=pinned_ids,
            hidden_product_ids=hidden_ids,
        )
        return Response({
            'count': total,
            'limit': preview_limit,
            'products': ProductSerializer(
                products, many=True, context={'request': request}
            ).data,
        })



class AdminTagListView(APIView):
    """List / create merchandising tags."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        tags = Tag.objects.annotate(
            product_count=Count('products', filter=Q(products__is_active=True))
        ).order_by('name')
        return Response([
            {
                'id': tag.id,
                'name': tag.name,
                'slug': tag.slug,
                'product_count': tag.product_count,
            }
            for tag in tags
        ])

    def post(self, request):
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'name': 'Required.'}, status=400)
        slug = slugify(request.data.get('slug') or name)
        tag, created = Tag.objects.get_or_create(
            slug=slug, defaults={'name': name}
        )
        return Response(
            {'id': tag.id, 'name': tag.name, 'slug': tag.slug},
            status=201 if created else 200,
        )


class AdminTagDetailView(APIView):
    """Retrieve / rename / delete a tag."""

    permission_classes = [IsAdminUser]

    def _get_tag(self, pk):
        try:
            return Tag.objects.get(pk=pk)
        except Tag.DoesNotExist:
            return None

    def get(self, request, pk):
        tag = self._get_tag(pk)
        if tag is None:
            return Response({'detail': 'Not found.'}, status=404)
        return Response({
            'id': tag.id,
            'name': tag.name,
            'slug': tag.slug,
            'product_count': tag.products.filter(is_active=True).count(),
        })

    def patch(self, request, pk):
        tag = self._get_tag(pk)
        if tag is None:
            return Response({'detail': 'Not found.'}, status=404)
        if 'name' in request.data:
            tag.name = request.data.get('name') or tag.name
        if 'slug' in request.data:
            new_slug = slugify(request.data.get('slug') or tag.name)
            if new_slug and new_slug != tag.slug:
                if Tag.objects.filter(slug=new_slug).exclude(pk=tag.pk).exists():
                    return Response({'slug': 'Already in use.'}, status=400)
                tag.slug = new_slug
        tag.save()
        return Response({'id': tag.id, 'name': tag.name, 'slug': tag.slug})

    def delete(self, request, pk):
        tag = self._get_tag(pk)
        if tag is None:
            return Response({'detail': 'Not found.'}, status=404)
        tag.delete()
        return Response(status=204)
