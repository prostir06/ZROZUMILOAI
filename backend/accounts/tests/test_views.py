"""API tests for auth endpoints (register, login, config, password)."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import ApiKey

User = get_user_model()

STRONG_PASSWORD = 'StrongPass1!'

NO_THROTTLE = {
    'REST_FRAMEWORK': {
        **settings.REST_FRAMEWORK,
        'DEFAULT_THROTTLE_RATES': {
            **settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'],
            'auth_login': '10000/minute',
            'auth_register': '10000/minute',
        },
    },
}


class AuthConfigTests(APITestCase):
    """Public auth config."""

    def test_auth_config_public(self):
        url = reverse('auth_config')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('allow_registration', response.data)


@override_settings(**NO_THROTTLE)
class RegisterTests(APITestCase):
    """User registration."""

    def _register_payload(self, **overrides):
        data = {
            'username': 'newuser',
            'email': 'new@test.com',
            'password': STRONG_PASSWORD,
            'password_confirm': STRONG_PASSWORD,
        }
        data.update(overrides)
        return data

    @override_settings(ALLOW_REGISTRATION=True)
    def test_register_success(self):
        response = self.client.post(
            reverse('register'),
            self._register_payload(),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['api_key'].startswith('zai_'))
        self.assertTrue(
            ApiKey.objects.filter(user__username='newuser').exists(),
        )

    @override_settings(ALLOW_REGISTRATION=False)
    def test_register_disabled(self):
        response = self.client.post(
            reverse('register'),
            self._register_payload(),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(ALLOW_REGISTRATION=True)
    def test_register_password_mismatch(self):
        response = self.client.post(
            reverse('register'),
            self._register_payload(password_confirm='OtherPass1!'),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_confirm', response.data)


@override_settings(**NO_THROTTLE)
class LoginTests(APITestCase):
    """JWT login."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='loginuser',
            password=STRONG_PASSWORD,
        )

    def test_login_success(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'loginuser', 'password': STRONG_PASSWORD},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['username'], 'loginuser')

    def test_login_wrong_password(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'loginuser', 'password': 'wrong'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CurrentUserTests(APITestCase):
    """Authenticated profile endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='meuser',
            password=STRONG_PASSWORD,
        )

    def test_me_requires_auth(self):
        response = self.client.get(reverse('current_user'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse('change_password'),
            {
                'current_password': STRONG_PASSWORD,
                'new_password': 'NewStrong1!',
                'new_password_confirm': 'NewStrong1!',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewStrong1!'))


class UserDetailGuardTests(APITestCase):
    """Захист UserDetailView від self-demote / видалення останнього su."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin_guard',
            email='admin_guard@test.com',
            password=STRONG_PASSWORD,
        )
        self.client.force_authenticate(user=self.admin)

    def test_cannot_demote_self(self):
        response = self.client.patch(
            reverse('user_delete', kwargs={'user_id': self.admin.pk}),
            {'is_staff': False},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_staff)

    def test_cannot_delete_self(self):
        response = self.client.delete(
            reverse('user_delete', kwargs={'user_id': self.admin.pk}),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_cannot_delete_last_superuser(self):
        response = self.client.delete(
            reverse('user_delete', kwargs={'user_id': self.admin.pk}),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_can_delete_other_user_when_two_superusers(self):
        other = User.objects.create_superuser(
            username='other_su',
            email='other_su@test.com',
            password=STRONG_PASSWORD,
        )
        response = self.client.delete(
            reverse('user_delete', kwargs={'user_id': other.pk}),
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=other.pk).exists())
