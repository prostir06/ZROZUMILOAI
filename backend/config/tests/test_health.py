"""Unit-тести /api/health/."""
from django.test import TestCase
from django.urls import reverse


class HealthEndpointTests(TestCase):
    """Health має відповідати без auth."""

    def test_health_returns_json(self):
        response = self.client.get(reverse('api_health'))
        self.assertIn(response.status_code, (200, 503))
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('database', data)
