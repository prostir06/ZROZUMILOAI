"""Unit-тести /api/health/."""
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse


class HealthEndpointTests(TestCase):
    """Health має відповідати без auth і відображати реальний стан БД."""

    def test_health_ok_when_database_available(self):
        response = self.client.get(reverse('api_health'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['database'], 'ok')
        self.assertIn(data.get('cache'), ('ok', 'miss', 'error', 'unknown'))

    @patch('config.health.connection')
    def test_health_degraded_when_database_fails(self, mock_connection):
        mock_connection.ensure_connection.side_effect = DatabaseError('down')
        response = self.client.get(reverse('api_health'))
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data['status'], 'degraded')
        self.assertEqual(data['database'], 'error')
