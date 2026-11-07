"""Unit-тести для фабрики LLM-провайдерів."""
from unittest.mock import patch

import requests
from django.test import SimpleTestCase

from llm.factory import list_all_models, resolve_provider
from llm.ollama_provider import OllamaProvider


class ListAllModelsTests(SimpleTestCase):
    @patch('llm.factory.OllamaProvider')
    def test_includes_only_ollama_models(self, mock_provider_cls):
        mock_provider_cls.provider_id = 'ollama'
        mock_provider_cls.return_value.list_models.return_value = {
            'models': [{'name': 'llama3', 'size': 100}],
        }
        data = list_all_models()
        names = [model['name'] for model in data['models']]
        self.assertEqual(names, ['llama3'])
        self.assertEqual(data['models'][0]['provider'], 'ollama')

    @patch('llm.factory.OllamaProvider')
    def test_ollama_failure_returns_empty_list(self, mock_provider_cls):
        mock_provider_cls.return_value.list_models.side_effect = (
            requests.RequestException('down')
        )
        data = list_all_models()
        self.assertEqual(data['models'], [])


class ResolveProviderTests(SimpleTestCase):
    def test_gemini_model_name_still_uses_ollama(self):
        provider = resolve_provider(model_name='gemini-2.0-flash')
        self.assertIsInstance(provider, OllamaProvider)
