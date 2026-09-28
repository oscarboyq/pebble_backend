from rest_framework import serializers

from .models import SmartCollection, SmartCollectionRule


class SmartCollectionRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmartCollectionRule
        fields = ['id', 'order', 'field', 'operator', 'value']


class SmartCollectionSerializer(serializers.ModelSerializer):
    rules = SmartCollectionRuleSerializer(many=True, read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = SmartCollection
        fields = [
            'id', 'name', 'slug', 'description', 'image', 'is_featured', 'position',
            'is_active', 'collection_type',
            'match_mode', 'sort', 'limit', 'rules', 'created_at', 'updated_at',
        ]

    def get_image(self, obj):
        request = self.context.get('request')
        url = obj.image.url if obj.image else None
        if url and request:
            return request.build_absolute_uri(url)
        return url
