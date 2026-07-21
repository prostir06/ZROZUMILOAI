"""Unit-тести ClientIPScopedRateThrottle."""
from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, override_settings
from rest_framework.views import APIView

from accounts.throttling import ClientIPScopedRateThrottle

User = get_user_model()


class _DummyView(APIView):
    throttle_scope = 'user_chat'


class ClientIPScopedRateThrottleTests(SimpleTestCase):
    """Перевірка ключа throttle: user pk або IP з trusted proxy."""

    def setUp(self):
        self.factory = RequestFactory()
        self.throttle = ClientIPScopedRateThrottle()
        self.view = _DummyView()

    def test_authenticated_uses_user_pk(self):
        user = User(pk=42, username='throttle_user')
        request = self.factory.get('/api/ollama/chat/')
        request.user = user
        self.assertEqual(self.throttle.get_ident(request), '42')

    @override_settings(TRUST_X_FORWARDED_FOR=False)
    def test_ignores_forwarded_when_untrusted(self):
        request = self.factory.get(
            '/api/ollama/chat/',
            HTTP_X_FORWARDED_FOR='203.0.113.10, 10.0.0.1',
            REMOTE_ADDR='127.0.0.1',
        )
        request.user = type('Anon', (), {'is_authenticated': False})()
        ident = self.throttle.get_ident(request)
        self.assertNotEqual(ident, '203.0.113.10')

    @override_settings(TRUST_X_FORWARDED_FOR=True)
    def test_uses_first_forwarded_hop(self):
        request = self.factory.get(
            '/api/ollama/chat/',
            HTTP_X_FORWARDED_FOR='203.0.113.10, 10.0.0.1',
            REMOTE_ADDR='127.0.0.1',
        )
        request.user = type('Anon', (), {'is_authenticated': False})()
        self.assertEqual(self.throttle.get_ident(request), '203.0.113.10')

    @override_settings(TRUST_X_FORWARDED_FOR=True)
    def test_falls_back_to_real_ip(self):
        request = self.factory.get(
            '/api/ollama/chat/',
            HTTP_X_REAL_IP='198.51.100.7',
            REMOTE_ADDR='127.0.0.1',
        )
        request.user = type('Anon', (), {'is_authenticated': False})()
        self.assertEqual(self.throttle.get_ident(request), '198.51.100.7')
