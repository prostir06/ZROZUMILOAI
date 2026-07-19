"""Unit-тести для спільної точки чату run_chat."""
import json
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status

from llm.base import LLMProviderError
from llm.chat import run_chat
from workspaces.models import Workspace

User = get_user_model()


class RunChatTests(TestCase):
    """Тести run_chat: stream, non-stream, обробка помилок."""

    def setUp(self):
        self.user = User.objects.create_user(username='chat_user', password='pass')
        self.workspace = Workspace.objects.create(
            name='Test WS',
            model_names=['llama3'],
        )

    @patch('llm.chat.resolve_provider')
    @patch('llm.chat.prepare_chat_messages')
    @patch('llm.chat.log_workspace_chat_exchange')
    def test_non_stream_success(self, mock_log, mock_prepare, mock_resolve):
        """Нестрімінговий чат повертає JSON відповіді провайдера."""
        mock_prepare.return_value = [{'role': 'user', 'content': 'Hi'}]
        provider = MagicMock()
        provider.chat.return_value = {
            'message': {'role': 'assistant', 'content': 'Hello'},
            'done': True,
        }
        mock_resolve.return_value = provider

        response = run_chat(
            model='llama3',
            messages=[{'role': 'user', 'content': 'Hi'}],
            stream=False,
            workspace=self.workspace,
            user=self.user,
            prompt='Hi',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message']['content'], 'Hello')
        mock_log.assert_called_once()

    @patch('llm.chat.resolve_provider')
    @patch('llm.chat.prepare_chat_messages')
    def test_non_stream_provider_error(self, mock_prepare, mock_resolve):
        """LLMProviderError → HTTP 503 з повідомленням."""
        mock_prepare.return_value = [{'role': 'user', 'content': 'Hi'}]
        provider = MagicMock()
        provider.chat.side_effect = LLMProviderError('Gemini недоступний')
        mock_resolve.return_value = provider

        response = run_chat(
            model='llama3',
            messages=[{'role': 'user', 'content': 'Hi'}],
            stream=False,
            workspace=self.workspace,
            user=self.user,
            prompt='Hi',
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data['error'], 'Gemini недоступний')

    @patch('llm.chat.resolve_provider')
    @patch('llm.chat.prepare_chat_messages')
    def test_non_stream_request_exception(self, mock_prepare, mock_resolve):
        """RequestException від провайдера → HTTP 503."""
        mock_prepare.return_value = [{'role': 'user', 'content': 'Hi'}]
        provider = MagicMock()
        provider.chat.side_effect = requests.RequestException('connection refused')
        mock_resolve.return_value = provider

        response = run_chat(
            model='llama3',
            messages=[{'role': 'user', 'content': 'Hi'}],
            stream=False,
            workspace=self.workspace,
            user=self.user,
            prompt='Hi',
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('connection refused', response.data['error'])

    @patch('llm.chat.resolve_provider')
    @patch('llm.chat.prepare_chat_messages')
    @patch('llm.chat.log_workspace_chat_exchange')
    def test_stream_yields_sse_chunks(self, mock_log, mock_prepare, mock_resolve):
        """Стрімінг повертає StreamingHttpResponse з SSE data: рядками."""
        mock_prepare.return_value = [{'role': 'user', 'content': 'Hi'}]
        chunk = json.dumps({
            'message': {'role': 'assistant', 'content': 'Hi'},
            'done': False,
        })
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [chunk.encode('utf-8')]

        provider = MagicMock()
        provider.chat.return_value = mock_response
        mock_resolve.return_value = provider

        response = run_chat(
            model='llama3',
            messages=[{'role': 'user', 'content': 'Hi'}],
            stream=True,
            workspace=self.workspace,
            user=self.user,
            prompt='Hi',
        )

        body = b''.join(response.streaming_content).decode('utf-8')
        self.assertIn('data:', body)
        self.assertIn('Hi', body)
        mock_log.assert_called_once()

    @patch('llm.chat.resolve_provider')
    @patch('llm.chat.prepare_chat_messages')
    def test_stream_provider_error_in_sse(self, mock_prepare, mock_resolve):
        """Помилка під час стріму передається як SSE data: {error}."""
        mock_prepare.return_value = [{'role': 'user', 'content': 'Hi'}]
        provider = MagicMock()
        provider.chat.side_effect = LLMProviderError('stream fail')
        mock_resolve.return_value = provider

        response = run_chat(
            model='llama3',
            messages=[{'role': 'user', 'content': 'Hi'}],
            stream=True,
            workspace=self.workspace,
            user=self.user,
            prompt='Hi',
        )

        body = b''.join(response.streaming_content).decode('utf-8')
        self.assertIn('stream fail', body)
