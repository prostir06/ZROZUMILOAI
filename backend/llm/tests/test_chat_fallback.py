"""Unit-тести для механізму fallback з Ollama на Gemini (Circuit Breaker)."""
import json
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status

from llm.base import LLMProviderError
from llm.chat import get_fallback_provider, run_chat
from llm.gemini_provider import GeminiProvider
from llm.ollama_provider import OllamaProvider
from workspaces.models import Workspace

User = get_user_model()


class FallbackProviderHelperTests(TestCase):
    """Тести для функції get_fallback_provider."""

    def setUp(self):
        self.workspace = Workspace.objects.create(name='Test WS')

    @override_settings(
        GEMINI_API_KEY='system-gemini-key',
        GEMINI_MODEL_NAMES=['gemini-2.0-flash', 'gemini-1.5-flash'],
        GEMINI_FALLBACK_MODEL='gemini-2.0-flash',
    )
    def test_fallback_activated_for_ollama_when_key_present(self):
        ollama = OllamaProvider()
        result = get_fallback_provider(self.workspace, ollama)
        self.assertIsNotNone(result)
        provider, model = result
        self.assertIsInstance(provider, GeminiProvider)
        self.assertEqual(provider.api_key, 'system-gemini-key')
        self.assertEqual(model, 'gemini-2.0-flash')

    @override_settings(
        GEMINI_API_KEY='system-gemini-key',
        GEMINI_MODEL_NAMES=['gemini-2.0-flash'],
    )
    def test_fallback_uses_first_model_if_fallback_model_setting_not_set(self):
        ollama = OllamaProvider()
        result = get_fallback_provider(self.workspace, ollama)
        self.assertIsNotNone(result)
        _, model = result
        self.assertEqual(model, 'gemini-2.0-flash')

    @override_settings(GEMINI_API_KEY='')
    def test_no_fallback_when_gemini_key_empty(self):
        ollama = OllamaProvider()
        result = get_fallback_provider(self.workspace, ollama)
        self.assertIsNone(result)

    @override_settings(GEMINI_API_KEY='system-key')
    def test_no_fallback_when_primary_is_not_ollama(self):
        gemini = GeminiProvider(api_key='system-key')
        result = get_fallback_provider(self.workspace, gemini)
        self.assertIsNone(result)


class ChatFallbackExecutionTests(TestCase):
    """Тести автоматичного перемикання на Gemini при збої Ollama."""

    def setUp(self):
        self.user = User.objects.create_user(username='fallback_user', password='pass')
        self.workspace = Workspace.objects.create(name='Fallback WS')

    @override_settings(GEMINI_API_KEY='test-gemini-key')
    @patch('llm.chat.resolve_provider')
    @patch('llm.chat.prepare_chat_messages')
    @patch('llm.chat.log_workspace_chat_exchange')
    @patch('llm.chat.GeminiProvider')
    def test_non_stream_fallback_on_ollama_connection_error(
        self,
        mock_gemini_cls,
        mock_log,
        mock_prepare,
        mock_resolve,
    ):
        mock_prepare.return_value = ([{'role': 'user', 'content': 'Привіт'}], [])
        ollama_mock = MagicMock(spec=OllamaProvider)
        ollama_mock.chat.side_effect = requests.exceptions.ConnectionError('Ollama down')
        mock_resolve.return_value = ollama_mock

        gemini_mock = MagicMock(spec=GeminiProvider)
        gemini_mock.chat.return_value = {
            'message': {'role': 'assistant', 'content': 'Відповідь від Gemini'},
            'done': True,
        }
        mock_gemini_cls.return_value = gemini_mock
        mock_log.return_value = MagicMock(pk=101)

        response = run_chat(
            model='llama3',
            messages=[{'role': 'user', 'content': 'Привіт'}],
            stream=False,
            workspace=self.workspace,
            user=self.user,
            prompt='Привіт',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message']['content'], 'Відповідь від Gemini')
        self.assertTrue(response.data.get('provider_fallback'))
        self.assertEqual(response.data.get('log_id'), 101)
        gemini_mock.chat.assert_called_once()

    @override_settings(GEMINI_API_KEY='test-gemini-key')
    @patch('llm.chat.resolve_provider')
    @patch('llm.chat.prepare_chat_messages')
    @patch('llm.chat.log_workspace_chat_exchange')
    @patch('llm.chat.GeminiProvider')
    def test_stream_fallback_on_ollama_connection_error(
        self,
        mock_gemini_cls,
        mock_log,
        mock_prepare,
        mock_resolve,
    ):
        mock_prepare.return_value = ([{'role': 'user', 'content': 'Привіт'}], [])
        ollama_mock = MagicMock(spec=OllamaProvider)
        ollama_mock.chat.side_effect = requests.exceptions.ConnectionError('Ollama unreachable')
        mock_resolve.return_value = ollama_mock

        chunk = json.dumps({
            'message': {'role': 'assistant', 'content': 'Gemini stream token'},
            'done': False,
        })
        gemini_stream_resp = MagicMock()
        gemini_stream_resp.iter_lines.return_value = [chunk.encode('utf-8')]

        gemini_mock = MagicMock(spec=GeminiProvider)
        gemini_mock.chat.return_value = gemini_stream_resp
        mock_gemini_cls.return_value = gemini_mock
        mock_log.return_value = MagicMock(pk=202)

        response = run_chat(
            model='llama3',
            messages=[{'role': 'user', 'content': 'Привіт'}],
            stream=True,
            workspace=self.workspace,
            user=self.user,
            prompt='Привіт',
        )

        lines = [
            line.decode('utf-8')
            for line in response.streaming_content
            if line
        ]
        body = ''.join(lines)
        self.assertIn('provider_fallback', body)
        self.assertIn('Gemini stream token', body)
        self.assertIn('202', body)

        # Перевіряємо першу подію fallback сповіщення
        fallback_notice = json.loads(lines[0].replace('data: ', '').strip())
        self.assertTrue(fallback_notice.get('provider_fallback'))
        self.assertIn('fallback_model', fallback_notice)

        # Перевіряємо фінальний metadata payload
        final_meta = json.loads(lines[-1].replace('data: ', '').strip())
        self.assertEqual(final_meta.get('log_id'), 202)
        self.assertTrue(final_meta.get('provider_fallback'))

    @override_settings(GEMINI_API_KEY='')
    @patch('llm.chat.resolve_provider')
    @patch('llm.chat.prepare_chat_messages')
    def test_no_fallback_when_gemini_not_configured(self, mock_prepare, mock_resolve):
        mock_prepare.return_value = ([{'role': 'user', 'content': 'Привіт'}], [])
        ollama_mock = MagicMock(spec=OllamaProvider)
        ollama_mock.chat.side_effect = requests.exceptions.ConnectionError('Ollama down')
        mock_resolve.return_value = ollama_mock

        response = run_chat(
            model='llama3',
            messages=[{'role': 'user', 'content': 'Привіт'}],
            stream=False,
            workspace=self.workspace,
            user=self.user,
            prompt='Привіт',
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('Ollama down', response.data['error'])

    @override_settings(GEMINI_API_KEY='test-key')
    @patch('llm.chat.resolve_provider')
    @patch('llm.chat.prepare_chat_messages')
    def test_no_fallback_when_provider_is_already_gemini(self, mock_prepare, mock_resolve):
        mock_prepare.return_value = ([{'role': 'user', 'content': 'Привіт'}], [])
        gemini_mock = MagicMock(spec=GeminiProvider)
        gemini_mock.chat.side_effect = LLMProviderError('Gemini rate limit exceeded')
        mock_resolve.return_value = gemini_mock

        response = run_chat(
            model='gemini-2.0-flash',
            messages=[{'role': 'user', 'content': 'Привіт'}],
            stream=False,
            workspace=self.workspace,
            user=self.user,
            prompt='Привіт',
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data['error'], 'Gemini rate limit exceeded')

    @override_settings(GEMINI_API_KEY='test-gemini-key')
    @patch('llm.chat.resolve_provider')
    @patch('llm.chat.prepare_chat_messages')
    @patch('llm.chat.GeminiProvider')
    def test_double_failure_non_stream_returns_clean_503(
        self,
        mock_gemini_cls,
        mock_prepare,
        mock_resolve,
    ):
        mock_prepare.return_value = ([{'role': 'user', 'content': 'Привіт'}], [])
        ollama_mock = MagicMock(spec=OllamaProvider)
        ollama_mock.chat.side_effect = requests.exceptions.ConnectionError('Ollama unreachable')
        mock_resolve.return_value = ollama_mock

        gemini_mock = MagicMock(spec=GeminiProvider)
        gemini_mock.chat.side_effect = LLMProviderError('Gemini 500 error')
        mock_gemini_cls.return_value = gemini_mock

        response = run_chat(
            model='llama3',
            messages=[{'role': 'user', 'content': 'Привіт'}],
            stream=False,
            workspace=self.workspace,
            user=self.user,
            prompt='Привіт',
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data['error'], 'Gemini 500 error')

    @override_settings(GEMINI_API_KEY='test-gemini-key')
    @patch('llm.chat.resolve_provider')
    @patch('llm.chat.prepare_chat_messages')
    @patch('llm.chat.GeminiProvider')
    def test_double_failure_stream_returns_clean_sse_error(
        self,
        mock_gemini_cls,
        mock_prepare,
        mock_resolve,
    ):
        mock_prepare.return_value = ([{'role': 'user', 'content': 'Привіт'}], [])
        ollama_mock = MagicMock(spec=OllamaProvider)
        ollama_mock.chat.side_effect = requests.exceptions.ConnectionError('Ollama unreachable')
        mock_resolve.return_value = ollama_mock

        gemini_mock = MagicMock(spec=GeminiProvider)
        gemini_mock.chat.side_effect = LLMProviderError('Gemini stream failed')
        mock_gemini_cls.return_value = gemini_mock

        response = run_chat(
            model='llama3',
            messages=[{'role': 'user', 'content': 'Привіт'}],
            stream=True,
            workspace=self.workspace,
            user=self.user,
            prompt='Привіт',
        )

        body = b''.join(response.streaming_content).decode('utf-8')
        self.assertIn('Gemini stream failed', body)
