from unittest.mock import patch

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
