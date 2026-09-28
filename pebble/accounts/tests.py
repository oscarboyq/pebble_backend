import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


@override_settings(
    STOREFRONT_URL='http://localhost:3000',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class PasswordResetTests(TestCase):
    def setUp(self):
        self.client = APIClient(REMOTE_ADDR=self._testMethodName)
        self.user = User.objects.create_user(
            username='buyer@example.com',
            email='buyer@example.com',
            password='OldSecurePass12!',
        )

    def test_request_uses_generic_response_and_emails_only_existing_user(self):
        sent = self.client.post(
            '/api/auth/password-reset/', {'email': 'buyer@example.com'}
        )
        unknown = self.client.post(
            '/api/auth/password-reset/', {'email': 'missing@example.com'}
        )
        self.assertEqual(sent.status_code, 200)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(sent.json(), unknown.json())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('http://localhost:3000/reset-password/', mail.outbox[0].body)

    def test_valid_token_changes_password_once(self):
        old_refresh = RefreshToken.for_user(self.user)
        old_access = str(old_refresh.access_token)
        self.client.post('/api/auth/password-reset/', {'email': self.user.email})
        link = re.search(
            r'/reset-password/([^/\s]+)/([^/\s]+)', mail.outbox[0].body
        )
        self.assertIsNotNone(link)
        payload = {
            'uid': link.group(1),
            'token': link.group(2),
            'new_password': 'NewSecurePass12!',
            'confirm_password': 'NewSecurePass12!',
        }
        weak = self.client.post(
            '/api/auth/password-reset/confirm/',
            {**payload, 'new_password': '123', 'confirm_password': '123'},
        )
        self.assertEqual(weak.status_code, 400)
        success = self.client.post('/api/auth/password-reset/confirm/', payload)
        self.assertEqual(success.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSecurePass12!'))
        reused = self.client.post('/api/auth/password-reset/confirm/', payload)
        self.assertEqual(reused.status_code, 400)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {old_access}')
        protected = self.client.post('/api/auth/change-password/', {
            'current_password': 'OldSecurePass12!',
            'new_password': 'AnotherSecurePass12!',
        })
        self.assertEqual(protected.status_code, 401)
        self.client.credentials()
        refresh = self.client.post('/api/auth/token/refresh/', {
            'refresh': str(old_refresh),
        })
        self.assertEqual(refresh.status_code, 401)
        new_login = self.client.post('/api/auth/login/', {
            'username': self.user.username,
            'password': 'NewSecurePass12!',
        })
        self.assertEqual(new_login.status_code, 200)
        new_refresh = self.client.post('/api/auth/token/refresh/', {
            'refresh': new_login.json()['refresh'],
        })
        self.assertEqual(new_refresh.status_code, 200)

    def test_invalid_link_does_not_change_password(self):
        response = self.client.post(
            '/api/auth/password-reset/confirm/',
            {
                'uid': 'bad',
                'token': 'bad',
                'new_password': 'NewSecurePass12!',
                'confirm_password': 'NewSecurePass12!',
            },
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OldSecurePass12!'))

    def test_expired_link_is_rejected(self):
        self.client.post('/api/auth/password-reset/', {'email': self.user.email})
        link = re.search(
            r'/reset-password/([^/\s]+)/([^/\s]+)', mail.outbox[0].body
        )
        two_hours_later = default_token_generator._now() + timedelta(hours=2)
        with patch.object(default_token_generator, '_now', return_value=two_hours_later):
            result = self.client.post('/api/auth/password-reset/confirm/', {
                'uid': link.group(1),
                'token': link.group(2),
                'new_password': 'NewSecurePass12!',
                'confirm_password': 'NewSecurePass12!',
            })
        self.assertEqual(result.status_code, 400)

    def test_request_is_rate_limited(self):
        for _ in range(5):
            result = self.client.post('/api/auth/password-reset/', {
                'email': 'missing@example.com',
            })
            self.assertEqual(result.status_code, 200)
        blocked = self.client.post('/api/auth/password-reset/', {
            'email': 'missing@example.com',
        })
        self.assertEqual(blocked.status_code, 429)
