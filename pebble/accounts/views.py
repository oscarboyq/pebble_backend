from rest_framework.views import APIView
from django.contrib.auth.models import User
from .serializers import RegisterSerializer, UpdateProfileSerializer, ChangePasswordSerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken 
from rest_framework_simplejwt.views import TokenObtainPairView as BaseTokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import UserProfile
from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework.throttling import ScopedRateThrottle

class RegisterView(APIView):
    permission_classes = [AllowAny] # no token required to register

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Generate JWT token for the new user
            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class MeView(APIView):
    permission_classes = [IsAuthenticated] # token required

    def get(self, request):
        user = request.user 
        profile = user.profile
        return Response({
            'id':         user.id,
            'email':      user.email,
            'first_name': user.first_name,
            'last_name':  user.last_name,
            'phone':      profile.phone,
            'gender':     profile.gender,
            'birthday':   str(profile.birthday) if profile.birthday else None,
            'newsletter_opt_in': profile.newsletter_opt_in,
            'address_line1': profile.address_line1,
            'address_line2': profile.address_line2,
            'city':       profile.city,
            'state':      profile.state,
            'zip_code':   profile.zip_code,
            'country':    profile.country,
        })
    

    def patch(self, request):
        serializer = UpdateProfileSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user 
        profile = user.profile
        data = serializer.validated_data
        
        # Update User fields
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        user.save()

        # Update UserProfile fields
        profile_fields = ['phone', 'gender', 'birthday', 'address_line1',
                          'address_line2', 'city', 'state', 'zip_code', 'country']
        
        for field in profile_fields:
            if field in data:
                setattr(profile, field, data[field])
        profile.save()

        return Response({
            'id':         user.id,
            'email':      user.email,
            'first_name': user.first_name,
            'last_name':  user.last_name,
            'phone':      profile.phone,
            'gender':     profile.gender,
            'birthday':   str(profile.birthday) if profile.birthday else None,
            'newsletter_opt_in': profile.newsletter_opt_in,
            'address_line1': profile.address_line1,
            'address_line2': profile.address_line2,
            'city':       profile.city,
            'state':      profile.state,
            'zip_code':   profile.zip_code,
            'country':    profile.country,
        })
    

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data) 

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user 
        if not user.check_password(serializer.validated_data['current_password']):
            return Response(
                {'current_password': 'Incorrect password.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response({'detail': 'Password changed successfully.'})
    
class AdminTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs) 
        user = self.user
        data['is_staff'] = user.is_staff
        data['user'] = {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }
        return data
    
class LoginView(BaseTokenObtainPairView):
    serializer_class = AdminTokenObtainPairSerializer


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        form = PasswordResetForm(data={'email': request.data.get('email', '')})
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
        form.save(
            request=request._request,
            use_https=settings.STOREFRONT_URL.startswith('https://'),
            email_template_name='accounts/password_reset_email.txt',
            subject_template_name='accounts/password_reset_subject.txt',
            extra_email_context={'storefront_url': settings.STOREFRONT_URL},
        )
        return Response({
            'detail': 'If an account uses that email, a reset link has been sent.'
        })


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset_confirm'

    def post(self, request):
        try:
            uid = force_str(urlsafe_base64_decode(request.data.get('uid', '')))
            user = get_user_model().objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
            user = None

        token = request.data.get('token', '')
        if user is None or not default_token_generator.check_token(user, token):
            return Response(
                {'detail': 'This reset link is invalid or expired.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        form = SetPasswordForm(user, data={
            'new_password1': request.data.get('new_password', ''),
            'new_password2': request.data.get('confirm_password', ''),
        })
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
        form.save()
        return Response({'detail': 'Password updated. Please sign in.'})






