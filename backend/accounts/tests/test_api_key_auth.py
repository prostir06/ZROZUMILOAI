"""Tests for API key creation and authentication."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import ApiKey
from accounts.services import create_api_key

User = get_user_model()

STRONG_PASSWORD = 'StrongPass1!'

NO_THROTTLE = {
    'REST_FRAMEWORK': {
        **settings.REST_FRAMEWORK,
        'DEFAULT_THROTTLE_RATES': {
            **settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'],
            'auth_register': '10000/minute',
        },
    },
}


@override_settings(**NO_THROTTLE)
class ApiKeyAuthTests(APITestCase):
    """API key lifecycle and header auth."""

    @override_settings(ALLOW_REGISTRATION=True)
    def test_api_key_created_on_register(self):
        response = self.client.post(
            reverse('register'),
            {
                'username': 'apiuser',
                'email': 'api@test.com',
                'password': STRONG_PASSWORD,
                'password_confirm': STRONG_PASSWORD,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        raw_key = response.data['api_key']
        self.assertTrue(raw_key.startswith('zai_'))
        self.assertTrue(ApiKey.objects.filter(user__username='apiuser').exists())

    def test_api_key_auth_me(self):
        user = User.objects.create_user(username='keyuser', password=STRONG_PASSWORD)
        raw_key = create_api_key(user)
        response = self.client.get(
            reverse('current_user'),
            HTTP_AUTHORIZATION=f'Api-Key {raw_key}',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'keyuser')

    def test_invalid_api_key(self):
        response = self.client.get(
            reverse('current_user'),
            HTTP_AUTHORIZATION='Api-Key zai_invalid_key_value',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
