from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()


class OllamaHealthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='health_user', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch('ollama_proxy.views.OllamaProvider')
    def test_health_has_no_gemini(self, mock_provider_cls):
        mock_provider_cls.return_value.health.return_value = True
        mock_provider_cls.return_value.base_url = 'http://ollama:11434'
        response = self.client.get(reverse('ollama_health'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('gemini', response.data)
        self.assertTrue(response.data['ollama']['connected'])


class OllamaProxyErrorLoggingTests(TestCase):
    """Перевірка логування помилок Ollama у proxy views."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='ollama_admin',
            email='ollama_admin@example.com',
            password='pass',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @patch('ollama_proxy.views.list_all_models')
    def test_model_list_logs_warning_and_returns_503(self, mock_list_models):
        mock_list_models.side_effect = requests.RequestException('ollama unreachable')
        with self.assertLogs('ollama_proxy.views', level='WARNING') as captured:
            response = self.client.get(reverse('ollama_models'))
        self.assertEqual(response.status_code, 503)
        self.assertTrue(
            any('Failed to fetch Ollama model list' in msg for msg in captured.output),
        )

    @patch('ollama_proxy.views.OllamaService')
    def test_model_delete_logs_warning_and_returns_503(self, mock_service_cls):
        mock_service_cls.return_value.delete_model.side_effect = requests.RequestException(
            'delete timeout',
        )
        with self.assertLogs('ollama_proxy.views', level='WARNING') as captured:
            response = self.client.delete(
                reverse('ollama_delete'),
                {'name': 'llama3'},
                format='json',
            )
        self.assertEqual(response.status_code, 503)
        self.assertTrue(
            any('Failed to delete Ollama model llama3' in msg for msg in captured.output),
        )

    @patch('ollama_proxy.views.OllamaService')
    def test_model_pull_stream_logs_warning_and_yields_error(self, mock_service_cls):
        mock_service_cls.return_value.pull_model.side_effect = requests.RequestException(
            'pull connection reset',
        )
        response = self.client.post(
            reverse('ollama_pull'),
            {'name': 'llama3'},
            format='json',
        )
        with self.assertLogs('ollama_proxy.views', level='WARNING') as captured:
            body = b''.join(response.streaming_content).decode('utf-8')
        self.assertIn('pull connection reset', body)
        self.assertTrue(
            any('Ollama model pull stream failed for llama3' in msg for msg in captured.output),
        )
