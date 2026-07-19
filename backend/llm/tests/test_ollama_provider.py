"""Unit-тести для Ollama LLM адаптера."""
from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from llm.base import LLMProviderError
from llm.ollama_provider import OllamaProvider


class OllamaProviderTests(SimpleTestCase):
    """Тести мапінгу помилок Ollama → LLMProviderError."""

    @patch('llm.ollama_provider.OllamaService')
    def test_chat_maps_validation_error(self, mock_service_cls):
        """ValidationError від sanitize_messages стає LLMProviderError."""
        service = mock_service_cls.return_value
        service.chat.side_effect = ValidationError({'messages': 'Порожній вміст'})

        provider = OllamaProvider()

        with self.assertRaises(LLMProviderError) as ctx:
            provider.chat('llama3', [], stream=False)

        self.assertIn('Порожній', str(ctx.exception))

    @patch('llm.ollama_provider.OllamaService')
    def test_chat_maps_request_exception(self, mock_service_cls):
        """Мережева помилка Ollama стає LLMProviderError."""
        service = mock_service_cls.return_value
        service.chat.side_effect = requests.RequestException('Ollama: timeout')

        provider = OllamaProvider()

        with self.assertRaises(LLMProviderError) as ctx:
            provider.chat('llama3', [{'role': 'user', 'content': 'Hi'}], stream=False)

        self.assertIn('timeout', str(ctx.exception))

    @patch('llm.ollama_provider.OllamaService')
    def test_chat_stream_returns_raw_response(self, mock_service_cls):
        """При stream=True повертається сирий HTTP response без parse_json."""
        service = mock_service_cls.return_value
        mock_response = MagicMock()
        service.chat.return_value = mock_response

        provider = OllamaProvider()
        result = provider.chat(
            'llama3',
            [{'role': 'user', 'content': 'Hi'}],
            stream=True,
        )

        self.assertIs(result, mock_response)
        service.parse_json.assert_not_called()

    @patch('llm.ollama_provider.OllamaService')
    def test_chat_parse_json_error_mapped(self, mock_service_cls):
        """Некоректний JSON від Ollama → LLMProviderError."""
        service = mock_service_cls.return_value
        mock_http = MagicMock()
        service.chat.return_value = mock_http
        service.parse_json.side_effect = requests.RequestException(
            'Некоректна відповідь від Ollama',
        )

        provider = OllamaProvider()

        with self.assertRaises(LLMProviderError):
            provider.chat(
                'llama3',
                [{'role': 'user', 'content': 'Hi'}],
                stream=False,
            )
