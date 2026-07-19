"""Unit-тести для фабрики LLM-провайдерів."""
from unittest.mock import patch

import requests
from django.test import SimpleTestCase, override_settings

from llm.factory import list_all_models, list_gemini_models


@override_settings(GEMINI_MODEL_NAMES=['gemini-2.0-flash'])
class ListAllModelsTests(SimpleTestCase):
    """Тести агрегації моделей з Ollama та Gemini."""

    @patch('llm.factory.OllamaProvider')
    def test_includes_ollama_and_gemini_models(self, mock_provider_cls):
        """Успішний запит до Ollama + статичний список Gemini."""
        mock_provider_cls.return_value.list_models.return_value = {
            'models': [{'name': 'llama3', 'size': 100}],
        }

        data = list_all_models()
        names = [model['name'] for model in data['models']]

        self.assertIn('llama3', names)
        self.assertIn('gemini-2.0-flash', names)

    @patch('llm.factory.OllamaProvider')
    def test_ollama_failure_still_returns_gemini(self, mock_provider_cls):
        """При недоступній Ollama повертаються лише моделі Gemini."""
        mock_provider_cls.return_value.list_models.side_effect = (
            requests.RequestException('down')
        )

        data = list_all_models()
        names = [model['name'] for model in data['models']]

        self.assertEqual(names, ['gemini-2.0-flash'])

    def test_list_gemini_models_static(self):
        """list_gemini_models читає GEMINI_MODEL_NAMES."""
        models = list_gemini_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]['provider'], 'gemini')
