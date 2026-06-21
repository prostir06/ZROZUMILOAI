"""Unit-тести сервісу логування workspace chat."""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase

from chats.models import WorkspaceChatLog
from chats.services import (
    UNKNOWN_USER_LABEL,
    content_from_ollama_chunk,
    decode_stream_line,
    extract_prompt_from_messages,
    extract_response_from_ollama_payload,
    log_workspace_chat_exchange,
    sent_by_label_for_user,
)
from workspaces.models import Workspace

User = get_user_model()


class SentByLabelTests(TestCase):
    """Тести формування мітки автора."""

    def test_authenticated_user_with_full_name(self):
        """Повне ім'я має пріоритет над username."""
        user = User.objects.create_user(
            username='jdoe',
            password='pass',
            first_name='John',
            last_name='Doe',
        )
        self.assertEqual(sent_by_label_for_user(user), 'John Doe')

    def test_authenticated_user_username_fallback(self):
        """Без імені використовується username."""
        user = User.objects.create_user(username='jdoe', password='pass')
        self.assertEqual(sent_by_label_for_user(user), 'jdoe')

    def test_anonymous_returns_unknown(self):
        """Анонімний користувач → unknown user."""
        self.assertEqual(sent_by_label_for_user(None), UNKNOWN_USER_LABEL)


class ExtractPromptTests(TestCase):
    """Тести витягування prompt з messages."""

    def test_extracts_last_user_message(self):
        """Береться останнє user-повідомлення."""
        messages = [
            {'role': 'user', 'content': 'Перше'},
            {'role': 'assistant', 'content': 'Відповідь'},
            {'role': 'user', 'content': '  Друге  '},
        ]
        self.assertEqual(extract_prompt_from_messages(messages), 'Друге')

    def test_invalid_messages_returns_empty(self):
        """Некоректна структура → порожній рядок."""
        self.assertEqual(extract_prompt_from_messages(None), '')


class ExtractResponseTests(TestCase):
    """Тести парсингу відповіді Ollama."""

    def test_chat_message_format(self):
        """Формат chat API з message.content."""
        payload = {'message': {'role': 'assistant', 'content': 'Привіт'}}
        self.assertEqual(extract_response_from_ollama_payload(payload), 'Привіт')

    def test_generate_format(self):
        """Формат generate API з response."""
        self.assertEqual(
            extract_response_from_ollama_payload({'response': 'Текст'}),
            'Текст',
        )

    def test_invalid_payload(self):
        """Некоректний payload → порожній рядок."""
        self.assertEqual(extract_response_from_ollama_payload('bad'), '')
        self.assertEqual(extract_response_from_ollama_payload({}), '')


class OllamaChunkTests(TestCase):
    """Тести SSE-чанків Ollama."""

    def test_valid_chunk(self):
        """Валідний JSON-чанк."""
        raw = json.dumps({'message': {'content': 'Частина'}})
        self.assertEqual(content_from_ollama_chunk(raw), 'Частина')

    def test_invalid_chunk_returns_empty(self):
        """Пошкоджений JSON не ламає streaming."""
        self.assertEqual(content_from_ollama_chunk('{invalid'), '')


class DecodeStreamLineTests(TestCase):
    """Тести декодування SSE-рядків."""

    def test_decodes_utf8(self):
        """Коректний UTF-8."""
        self.assertEqual(decode_stream_line('data'.encode()), 'data')

    def test_invalid_utf8_returns_none(self):
        """Некоректний UTF-8 → None."""
        self.assertIsNone(decode_stream_line(b'\xff\xfe'))

    def test_empty_line_returns_none(self):
        """Порожній рядок → None."""
        self.assertIsNone(decode_stream_line(b''))


class LogWorkspaceChatExchangeTests(TestCase):
    """Тести збереження записів Chats Info."""

    def setUp(self):
        """Workspace для логів."""
        self.workspace = Workspace.objects.create(
            name='test-ws',
            model_names=['llama3'],
        )
        self.user = User.objects.create_user(username='logger', password='pass')

    def test_creates_log_entry(self):
        """Успішне збереження prompt/response."""
        entry = log_workspace_chat_exchange(
            workspace=self.workspace,
            user=self.user,
            prompt='  Запит  ',
            response='Відповідь',
        )
        self.assertIsNotNone(entry)
        self.assertEqual(WorkspaceChatLog.objects.count(), 1)
        self.assertEqual(entry.prompt, 'Запит')
        self.assertEqual(entry.sent_by, 'logger')

    def test_skips_empty_prompt(self):
        """Без prompt запис не створюється."""
        self.assertIsNone(
            log_workspace_chat_exchange(workspace=self.workspace, prompt='  '),
        )
        self.assertEqual(WorkspaceChatLog.objects.count(), 0)

    def test_skips_missing_workspace(self):
        """Без workspace запис не створюється."""
        self.assertIsNone(log_workspace_chat_exchange(workspace=None, prompt='Hi'))
        self.assertEqual(WorkspaceChatLog.objects.count(), 0)

    @patch('chats.services.WorkspaceChatLog.objects.create')
    def test_database_error_returns_none(self, mock_create):
        """Помилка БД не пробивається наверх."""
        mock_create.side_effect = DatabaseError('disk full')
        result = log_workspace_chat_exchange(
            workspace=self.workspace,
            prompt='Test',
        )
        self.assertIsNone(result)

    def test_widget_anonymous_user(self):
        """Widget без user → unknown user."""
        entry = log_workspace_chat_exchange(
            workspace=self.workspace,
            prompt='Widget msg',
            response='OK',
        )
        self.assertEqual(entry.sent_by, UNKNOWN_USER_LABEL)
        self.assertIsNone(entry.user)
