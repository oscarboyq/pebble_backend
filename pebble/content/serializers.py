from rest_framework import serializers

from .models import Page, Article


class PageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = ['id', 'title', 'slug', 'body', 'updated_at']


class ArticleListSerializer(serializers.ModelSerializer):
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            'id', 'blog_handle', 'title', 'slug', 'excerpt',
            'cover_image', 'author_name', 'published_at',
        ]

    def get_cover_image(self, obj):
        request = self.context.get('request')
        url = obj.cover_image.url if obj.cover_image else None
        if url and request:
            return request.build_absolute_uri(url)
        return url


class ArticleDetailSerializer(ArticleListSerializer):
    class Meta(ArticleListSerializer.Meta):
        fields = ArticleListSerializer.Meta.fields + ['body']
