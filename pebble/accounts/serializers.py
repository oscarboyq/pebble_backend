from .models import UserProfile
from rest_framework import serializers 
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password


class RegisterSerializer(serializers.Serializer):
    # User Fields
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6 ,write_only=True)
    first_name = serializers.CharField()
    last_name = serializers.CharField()

    # UserProfile Fields
    phone = serializers.CharField(required=False, default='')
    gender = serializers.CharField(required=False, default='')
    birthday = serializers.DateField(required=False, allow_null=True)
    newsletter_opt_in = serializers.BooleanField(default=True)
    address_line1 = serializers.CharField(required=False, default='')
    address_line2 = serializers.CharField(required=False, allow_blank=True, default='')
    city = serializers.CharField(required=False, default='')
    state = serializers.CharField(required=False, default='')
    zip_code = serializers.CharField(required=False, default='')
    country = serializers.CharField(required=False, default='United States')

    def validate_email(self, value):
        #check if email already exists
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email is already in use.")
        return value.lower()
    
    def create(self, validated_data):
        # pull out user fields
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name']
        )
        #create the linked user profile
        UserProfile.objects.create(
            user=user,
            phone=validated_data.get('phone', ''),
            gender=validated_data.get('gender', ''),
            birthday=validated_data.get('birthday'),
            newsletter_opt_in = validated_data.get('newsletter_opt_in', True),
            address_line1 = validated_data.get('address_line1', ''),
            address_line2 = validated_data.get('address_line2', ''),
            city = validated_data.get('city', ''),
            state = validated_data.get('state', ''),
            zip_code = validated_data.get('zip_code', ''),
            country = validated_data.get('country', 'United States')
        )
        return user
    
    

class UpdateProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    phone = serializers.CharField(required=False, allow_blank=True)
    gender = serializers.CharField(required=False, allow_blank=True)
    birthday = serializers.DateField(required=False, allow_null=True)
    address_line1 = serializers.CharField(required=False, allow_blank=True)
    address_line2 = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    state = serializers.CharField(required=False, allow_blank=True)
    zip_code = serializers.CharField(required=False, allow_blank=True)
    country = serializers.CharField(required=False, allow_blank=True)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField() 
    new_password = serializers.CharField(min_length=6)


class PasswordAwareTokenRefreshSerializer(TokenRefreshSerializer):
    """Reject refresh tokens issued before the user's latest password change."""

    def validate(self, attrs):
        refresh = self.token_class(attrs['refresh'])
        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)
        user = None
        if user_id is not None:
            user = get_user_model().objects.filter(
                **{api_settings.USER_ID_FIELD: user_id}
            ).first()
        claim = refresh.payload.get(api_settings.REVOKE_TOKEN_CLAIM, '')
        if user is None or not constant_time_compare(
            claim, get_md5_hash_password(user.password)
        ):
            raise AuthenticationFailed('Token is no longer valid.')
        return super().validate(attrs)
