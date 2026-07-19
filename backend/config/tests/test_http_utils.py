"""Unit-тести для HTTP-утиліт."""
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from config.http_utils import validate_chat_messages


class ValidateChatMessagesTests(SimpleTestCase):
    """Тести валідації структури повідомлень чату."""

    def test_valid_messages(self):
        """Коректний список повідомлень проходить валідацію."""
        messages = [
            {'role': 'user', 'content': 'Привіт'},
            {'role': 'assistant', 'content': 'Вітаю'},
        ]
        self.assertEqual(validate_chat_messages(messages), messages)

    def test_rejects_non_list(self):
        """Некоректний тип messages викликає ValidationError."""
        with self.assertRaises(ValidationError):
            validate_chat_messages('not a list')

    def test_rejects_invalid_role(self):
        """Невідома роль повідомлення відхиляється."""
        with self.assertRaises(ValidationError):
            validate_chat_messages([{'role': 'bot', 'content': 'test'}])

    def test_rejects_non_string_content(self):
        """Вміст повідомлення має бути рядком."""
        with self.assertRaises(ValidationError):
            validate_chat_messages([{'role': 'user', 'content': 123}])

    def test_allows_system_role(self):
        """Роль system допустима для Ollama."""
        messages = [{'role': 'system', 'content': 'You are helpful.'}]
        self.assertEqual(validate_chat_messages(messages), messages)

    def test_rejects_too_many_messages(self):
        """Перевищення CHAT_MAX_MESSAGES."""
        from django.test import override_settings

        with override_settings(CHAT_MAX_MESSAGES=2):
            with self.assertRaises(ValidationError):
                validate_chat_messages([
                    {'role': 'user', 'content': 'a'},
                    {'role': 'assistant', 'content': 'b'},
                    {'role': 'user', 'content': 'c'},
                ])

    def test_rejects_oversized_message(self):
        """Перевищення CHAT_MAX_MESSAGE_CHARS."""
        from django.test import override_settings

        with override_settings(CHAT_MAX_MESSAGE_CHARS=5):
            with self.assertRaises(ValidationError):
                validate_chat_messages([{'role': 'user', 'content': 'too-long'}])

    def test_validation_error_message_helper(self):
        """validation_error_message витягує перший detail."""
        from config.http_utils import validation_error_message

        err = ValidationError({'messages': ['bad']})
        self.assertEqual(validation_error_message(err), 'bad')
