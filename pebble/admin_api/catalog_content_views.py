"""Typed owner APIs for Phase 2 catalog and editorial data."""

from django.db import transaction
from django.db import models
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Product, ProductLink
from products.models import SizeChart
from home import models as home_models


class ProductLinkSelectionSerializer(serializers.Serializer):
    product_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)

    def validate_product_ids(self, ids):
        source_id = self.context['source_id']
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('Each product may appear only once.')
        if source_id in ids:
            raise serializers.ValidationError('A product cannot link to itself.')
        found = set(Product.objects.filter(id__in=ids).values_list('id', flat=True))
        if found != set(ids):
            raise serializers.ValidationError('One or more products do not exist.')
        return ids


class AdminProductLinksView(APIView):
    permission_classes = [IsAdminUser]

    def _source(self, pk):
        return Product.objects.filter(pk=pk).first()

    def get(self, request, pk, intent):
        if intent not in dict(ProductLink.INTENTS):
            return Response({'intent': 'Invalid intent.'}, status=400)
        if not self._source(pk):
            return Response({'detail': 'Product not found.'}, status=404)
        links = ProductLink.objects.filter(source_id=pk, intent=intent).select_related('target')
        return Response({'intent': intent, 'product_ids': [link.target_id for link in links]})

    @transaction.atomic
    def put(self, request, pk, intent):
        if intent not in dict(ProductLink.INTENTS):
            return Response({'intent': 'Invalid intent.'}, status=400)
        if not self._source(pk):
            return Response({'detail': 'Product not found.'}, status=404)
        serializer = ProductLinkSelectionSerializer(data=request.data, context={'source_id': pk})
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data['product_ids']
        ProductLink.objects.filter(source_id=pk, intent=intent).delete()
        ProductLink.objects.bulk_create([
            ProductLink(source_id=pk, target_id=product_id, intent=intent, order=order)
            for order, product_id in enumerate(ids)
        ])
        return Response({'intent': intent, 'product_ids': ids})


class HotspotInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    desktop_x = serializers.FloatField(min_value=0, max_value=100, allow_null=True, required=False)
    desktop_y = serializers.FloatField(min_value=0, max_value=100, allow_null=True, required=False)
    mobile_x = serializers.FloatField(min_value=0, max_value=100, allow_null=True, required=False)
    mobile_y = serializers.FloatField(min_value=0, max_value=100, allow_null=True, required=False)

    def validate(self, attrs):
        for prefix in ('desktop', 'mobile'):
            if (attrs.get(prefix + '_x') is None) != (attrs.get(prefix + '_y') is None):
                raise serializers.ValidationError(f'{prefix} coordinates must be supplied together.')
        return attrs


class HotspotSelectionSerializer(serializers.Serializer):
    hotspots = HotspotInputSerializer(many=True, allow_empty=True)

    def validate_hotspots(self, hotspots):
        ids = [entry['product_id'] for entry in hotspots]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('Each product may appear only once per card.')
        found = set(Product.objects.filter(id__in=ids).values_list('id', flat=True))
        if found != set(ids):
            raise serializers.ValidationError('One or more products do not exist.')
        return hotspots


class AdminLookbookHotspotsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        if not home_models.LookbookCard.objects.filter(pk=pk).exists():
            return Response({'detail': 'Lookbook card not found.'}, status=404)
        return Response({'hotspots': [
            {'id': spot.id, 'product_id': spot.product_id, 'desktop_x': spot.desktop_x,
             'desktop_y': spot.desktop_y, 'mobile_x': spot.mobile_x,
             'mobile_y': spot.mobile_y, 'order': spot.order}
            for spot in home_models.LookbookHotspot.objects.filter(card_id=pk)
        ]})

    @transaction.atomic
    def put(self, request, pk):
        card = home_models.LookbookCard.objects.filter(pk=pk).first()
        if card is None:
            return Response({'detail': 'Lookbook card not found.'}, status=404)
        serializer = HotspotSelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entries = serializer.validated_data['hotspots']
        home_models.LookbookHotspot.objects.filter(card=card).delete()
        home_models.LookbookHotspot.objects.bulk_create([
            home_models.LookbookHotspot(card=card, order=order, **entry)
            for order, entry in enumerate(entries)
        ])
        card.tagged_products.set([entry['product_id'] for entry in entries])
        return self.get(request, pk)


EDITORIAL_MODELS = {
    'promo-bars': home_models.PromoBar,
    'store-settings': home_models.StoreSettings,
    'marquee-items': home_models.MarqueeItem,
    'header-menu': home_models.HeaderMenuItem,
    'trust-badges': home_models.TrustBadge,
    'footer-settings': home_models.FooterSettings,
    'footer-links': home_models.FooterLink,
    'footer-instagram-images': home_models.FooterInstagramImage,
    'banners': home_models.BannerSlide,
    'lookbook-cards': home_models.LookbookCard,
    'suggestion-sections': home_models.ProductSuggestionSection,
    'suggestion-steps': home_models.ProductSuggestionStep,
    'bundle-sections': home_models.ProductsBundleSection,
    'testimonial-sections': home_models.TestimonialsParallaxSection,
    'testimonial-items': home_models.TestimonialItem,
    'flex-sections': home_models.FlexCarouselSection,
    'pages-menu-settings': home_models.PagesMenuSetting,
    'size-charts': SizeChart,
    'new-in-cards': home_models.NewInShowcaseCard,
    'new-in-settings': home_models.NewInShowcaseSettings,
    'outfit-highlights': home_models.OutfitHighlightItem,
    'layered-cards': home_models.LayeredScrollingCard,
    'products-highlight': home_models.ProductsHighlightSection,
    'our-story': home_models.OurStorySection,
    'brand-pillars': home_models.BrandPillarItem,
    'flex-cards': home_models.FlexCarouselCard,
    'shop-promos': home_models.ShopMenuPromo,
    'collection-menu-links': home_models.CollectionsMenuLink,
    'collection-menu-promos': home_models.CollectionsMenuPromo,
    'pages-menu-cards': home_models.PagesMenuCard,
    'pages-menu-links': home_models.PagesMenuLink,
    'features-menu-items': home_models.FeaturesMenuItem,
    'features-menu-subitems': home_models.FeaturesMenuSubItem,
    'collection-menu-columns': home_models.CollectionsMenuColumn,
    'menu-sections': home_models.MegaMenuSection,
}

SINGLETON_MODELS = {
    home_models.PromoBar, home_models.StoreSettings,
    home_models.NewInShowcaseSettings,
    home_models.ProductsHighlightSection, home_models.ProductSuggestionSection,
    home_models.ProductsBundleSection, home_models.TestimonialsParallaxSection,
    home_models.OurStorySection, home_models.FlexCarouselSection,
    home_models.PagesMenuSetting, home_models.FooterSettings,
}

LINK_FIELDS = {
    home_models.BannerSlide: 'cta_link',
    home_models.NewInShowcaseCard: 'product_link',
    home_models.NewInShowcaseSettings: 'cta_link',
    home_models.OutfitHighlightItem: 'link_url',
    home_models.LayeredScrollingCard: 'link_url',
    home_models.ProductsHighlightSection: 'button_link',
    home_models.OurStorySection: 'button_link',
    home_models.BrandPillarItem: 'button_link',
    home_models.FlexCarouselCard: 'link',
    home_models.ShopMenuPromo: 'cta_link',
    home_models.CollectionsMenuLink: 'route',
    home_models.CollectionsMenuPromo: 'route',
    home_models.PagesMenuCard: 'route',
    home_models.PagesMenuLink: 'route',
    home_models.FeaturesMenuItem: 'route',
    home_models.FeaturesMenuSubItem: 'route',
    home_models.FooterLink: 'route',
}


class EditorialSerializer(serializers.ModelSerializer):
    def get_fields(self):
        fields = super().get_fields()
        link_field = LINK_FIELDS.get(self.Meta.model)
        if link_field in fields:
            fields[link_field].required = False
        return fields

    def validate(self, attrs):
        if self.instance is None:
            # DRF treats an omitted multipart checkbox as False. These forms
            # send only changed fields, so preserve each model's real default.
            for field in self.Meta.model._meta.fields:
                if isinstance(field, models.BooleanField) and field.name not in self.initial_data and field.has_default():
                    attrs[field.name] = field.get_default()
        if self.Meta.model is SizeChart:
            columns = attrs.get('columns', getattr(self.instance, 'columns', []))
            rows = attrs.get('rows', getattr(self.instance, 'rows', []))
            if not isinstance(columns, list) or any(not isinstance(value, str) for value in columns):
                raise serializers.ValidationError({'columns': 'Use a list of column headings.'})
            if not isinstance(rows, list) or any(not isinstance(row, list) or len(row) != len(columns) for row in rows):
                raise serializers.ValidationError({'rows': 'Each row must match the number of columns.'})
        if self.Meta.model is home_models.ProductsBundleSection:
            products = attrs.get('bundle_products')
            if products is not None and len(products) != 2:
                raise serializers.ValidationError({'bundle_products': 'Select exactly two products.'})
        product = attrs.get('destination_product', getattr(self.instance, 'destination_product', None))
        collection = attrs.get('destination_collection', getattr(self.instance, 'destination_collection', None))
        if product and collection:
            raise serializers.ValidationError('Choose a product or collection destination, not both.')
        product = attrs.get('product', getattr(self.instance, 'product', None)) if self.Meta.model is home_models.FooterLink else None
        collection = attrs.get('collection', getattr(self.instance, 'collection', None)) if self.Meta.model is home_models.FooterLink else None
        if product and collection:
            raise serializers.ValidationError('Choose a product or collection footer link, not both.')
        return attrs

    def _apply_destination(self, attrs):
        model = self.Meta.model
        link_field = LINK_FIELDS.get(model)
        if not link_field:
            return attrs
        product_key = 'product' if model is home_models.FooterLink else 'destination_product'
        collection_key = 'collection' if model is home_models.FooterLink else 'destination_collection'
        if product_key in attrs or collection_key in attrs:
            product = attrs.get(product_key, getattr(self.instance, product_key, None))
            collection = attrs.get(collection_key, getattr(self.instance, collection_key, None))
            if product:
                attrs[link_field] = f'/products/{product.slug}'
            elif collection:
                attrs[link_field] = f'/collections/{collection.slug}'
        return attrs

    def create(self, validated_data):
        return super().create(self._apply_destination(validated_data))

    def update(self, instance, validated_data):
        return super().update(instance, self._apply_destination(validated_data))


def serializer_for(model):
    class SpecificEditorialSerializer(EditorialSerializer):
        class Meta:
            fields = '__all__'
    SpecificEditorialSerializer.Meta.model = model
    return SpecificEditorialSerializer


class AdminEditorialSchemaView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, kind):
        model = EDITORIAL_MODELS.get(kind)
        if model is None:
            return Response({'detail': 'Unknown content type.'}, status=404)
        fields = []
        for field in model._meta.fields + model._meta.many_to_many:
            if field.primary_key or not field.editable or field.auto_created:
                continue
            if isinstance(field, models.ImageField):
                field_type = 'image'
            elif isinstance(field, models.BooleanField):
                field_type = 'boolean'
            elif isinstance(field, models.ForeignKey):
                field_type = 'relation'
            elif isinstance(field, models.ManyToManyField):
                field_type = 'products'
            elif isinstance(field, models.JSONField):
                field_type = 'json'
            elif isinstance(field, (models.IntegerField, models.FloatField, models.DecimalField)):
                field_type = 'number'
            elif isinstance(field, models.TextField):
                field_type = 'long_text'
            else:
                field_type = 'text'
            fields.append({
                'name': field.name,
                'label': str(field.verbose_name).capitalize(),
                'type': field_type,
                'required': not field.blank and not field.has_default(),
                'choices': [{'value': value, 'label': label} for value, label in (field.choices or [])],
                'relation': field.related_model._meta.model_name if field_type == 'relation' else None,
            })
        return Response({'kind': kind, 'fields': fields})


class AdminEditorialListView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request, kind):
        model = EDITORIAL_MODELS.get(kind)
        if model is None:
            return Response({'detail': 'Unknown content type.'}, status=404)
        return Response(serializer_for(model)(model.objects.all().order_by('id'), many=True, context={'request': request}).data)

    def post(self, request, kind):
        model = EDITORIAL_MODELS.get(kind)
        if model is None:
            return Response({'detail': 'Unknown content type.'}, status=404)
        if model in SINGLETON_MODELS and model.objects.exists():
            return Response({'detail': 'This section already exists; edit the existing record.'}, status=400)
        serializer = serializer_for(model)(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(serializer_for(model)(item, context={'request': request}).data, status=status.HTTP_201_CREATED)


class AdminEditorialDetailView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def _item(self, kind, pk):
        model = EDITORIAL_MODELS.get(kind)
        return (model.objects.filter(pk=pk).first() if model else None), model

    def get(self, request, kind, pk):
        item, model = self._item(kind, pk)
        if item is None:
            return Response({'detail': 'Not found.'}, status=404)
        return Response(serializer_for(model)(item, context={'request': request}).data)

    def patch(self, request, kind, pk):
        item, model = self._item(kind, pk)
        if item is None:
            return Response({'detail': 'Not found.'}, status=404)
        serializer = serializer_for(model)(item, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(serializer_for(model)(item, context={'request': request}).data)

    def delete(self, request, kind, pk):
        item, _ = self._item(kind, pk)
        if item is None:
            return Response({'detail': 'Not found.'}, status=404)
        item.delete()
        return Response(status=204)


class AdminNewsletterSubscribersView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response([
            {'id': item.id, 'email': item.email, 'is_active': item.is_active,
             'subscribed_at': item.subscribed_at, 'source': item.source}
            for item in home_models.NewsletterSubscriber.objects.all().order_by('-subscribed_at')
        ])

    def patch(self, request):
        subscriber = home_models.NewsletterSubscriber.objects.filter(pk=request.data.get('id')).first()
        if subscriber is None:
            return Response({'detail': 'Subscriber not found.'}, status=404)
        if not isinstance(request.data.get('is_active'), bool):
            return Response({'is_active': 'Must be a boolean.'}, status=400)
        subscriber.is_active = request.data['is_active']
        subscriber.save(update_fields=['is_active'])
        return Response({'id': subscriber.id, 'email': subscriber.email, 'is_active': subscriber.is_active})
