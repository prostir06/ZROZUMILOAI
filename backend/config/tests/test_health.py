"""Unit-тести /api/health/."""
from unittest.mock import patch

from django.core.cache import cache
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse


class HealthEndpointTests(TestCase):
    """Health має відповідати без auth і відображати стан БД, кешу та Ollama."""

    def setUp(self):
        cache.clear()

    @patch('config.health.OllamaService')
    def test_health_ok_when_database_and_ollama_available(self, mock_ollama_cls):
        mock_ollama_cls.return_value.health.return_value = True
        response = self.client.get(reverse('api_health'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['database'], 'ok')
        self.assertEqual(data['ollama'], 'ok')
        self.assertIn(data.get('cache'), ('ok', 'miss', 'error', 'unknown'))

    @patch('config.health.OllamaService')
    def test_health_degraded_200_by_default_and_503_with_strict_when_ollama_down(
        self,
        mock_ollama_cls,
    ):
        mock_ollama_cls.return_value.health.return_value = False

        res_default = self.client.get(reverse('api_health'))
        self.assertEqual(res_default.status_code, 200)
        self.assertEqual(res_default.json()['status'], 'degraded')
        self.assertEqual(res_default.json()['ollama'], 'error')

        res_strict = self.client.get(f"{reverse('api_health')}?strict=1")
        self.assertEqual(res_strict.status_code, 503)
        self.assertEqual(res_strict.json()['status'], 'degraded')
        self.assertEqual(res_strict.json()['ollama'], 'error')

    @patch('config.health.OllamaService')
    @patch('config.health.connection')
    def test_health_degraded_when_database_fails(
        self,
        mock_connection,
        mock_ollama_cls,
    ):
        mock_ollama_cls.return_value.health.return_value = True
        mock_connection.ensure_connection.side_effect = DatabaseError('down')
        response = self.client.get(reverse('api_health'))
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data['status'], 'degraded')
        self.assertEqual(data['database'], 'error')

    @patch('config.health.OllamaService')
    def test_check_ollama_status_caches_result_for_subsequent_calls(
        self,
        mock_ollama_cls,
    ):
        mock_ollama_cls.return_value.health.return_value = True

        res1 = self.client.get(reverse('api_health'))
        res2 = self.client.get(reverse('api_health'))

        self.assertEqual(res1.json()['ollama'], 'ok')
        self.assertEqual(res2.json()['ollama'], 'ok')
        self.assertEqual(mock_ollama_cls.return_value.health.call_count, 1)

