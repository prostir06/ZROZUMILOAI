"""Unit-тести для OllamaService."""
import json
from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase, override_settings

from ollama_proxy.services import OllamaService


@override_settings(OLLAMA_BASE_URL='http://ollama:11434')
class OllamaServiceTests(SimpleTestCase):
    """Тести HTTP-клієнта Ollama."""

    def test_base_url_strips_trailing_slash(self):
        """Завершальний слеш у base_url видаляється."""
        service = OllamaService(base_url='http://localhost:11434/')
        self.assertEqual(service.base_url, 'http://localhost:11434')

    @patch.object(requests.Session, 'request')
    def test_list_models_parses_json(self, mock_request):
        """list_models повертає розпарсений JSON."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'models': [{'name': 'llama3'}]}
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        service = OllamaService()
        data = service.list_models()

        self.assertEqual(data['models'][0]['name'], 'llama3')
        mock_request.assert_called_once()

    @patch.object(requests.Session, 'request')
    def test_health_returns_false_on_network_error(self, mock_request):
        """health() повертає False при мережевій помилці."""
        mock_request.side_effect = requests.ConnectionError('down')
        service = OllamaService()
        self.assertFalse(service.health())

    @patch.object(requests.Session, 'request')
    def test_parse_json_raises_on_invalid_body(self, mock_request):
        """parse_json викликає RequestException для некоректного JSON."""
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError('err', 'doc', 0)
        service = OllamaService()

        with self.assertRaises(requests.RequestException):
            service.parse_json(mock_response)
