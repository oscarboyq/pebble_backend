from rest_framework import serializers
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from content.models import Page


class OwnerPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = ('id', 'slug', 'title', 'body', 'is_published', 'updated_at')
        read_only_fields = ('id', 'slug', 'is_published', 'updated_at')

    def validate(self, attrs):
        published = self.instance.is_published
        body = attrs.get('body', self.instance.body)
        if published and not body.strip():
            raise serializers.ValidationError({'body': 'Published pages need content.'})
        return attrs


class OwnerPageListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(OwnerPageSerializer(Page.objects.all(), many=True).data)


class OwnerPageDetailView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        page = Page.objects.filter(pk=pk).first()
        if page is None:
            return Response({'detail': 'Page not found.'}, status=404)
        serializer = OwnerPageSerializer(page, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
