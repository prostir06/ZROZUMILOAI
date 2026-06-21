"""Unit-тести Ollama payload helpers."""
from unittest.mock import MagicMock

import requests
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from ollama_proxy.ollama_utils import (
    normalize_model_name,
    parse_ollama_error,
    raise_for_ollama_status,
    sanitize_messages_for_ollama,
)


class OllamaUtilsTests(SimpleTestCase):
    def test_normalize_model_name_strips_whitespace(self):
        self.assertEqual(normalize_model_name('  gemma3  '), 'gemma3')

    def test_normalize_model_name_rejects_empty(self):
        with self.assertRaises(ValidationError):
            normalize_model_name('   ')

    def test_sanitize_messages_removes_empty_content(self):
        messages = [
            {'role': 'user', 'content': '  hi  '},
            {'role': 'assistant', 'content': ''},
        ]
        cleaned = sanitize_messages_for_ollama(messages)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]['content'], 'hi')

    def test_sanitize_messages_requires_user(self):
        with self.assertRaises(ValidationError):
            sanitize_messages_for_ollama([{'role': 'assistant', 'content': 'only bot'}])

    def test_parse_ollama_error_from_json(self):
        response = MagicMock()
        response.json.return_value = {'error': 'model is required'}
        response.text = ''
        self.assertEqual(parse_ollama_error(response), 'model is required')

    def test_raise_for_ollama_status_includes_body(self):
        response = MagicMock()
        response.ok = False
        response.status_code = 400
        response.json.return_value = {'error': 'model is required'}

        with self.assertRaises(requests.RequestException) as ctx:
            raise_for_ollama_status(response)

        self.assertIn('model is required', str(ctx.exception))
