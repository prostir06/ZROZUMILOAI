"""Unit-тести для chat serializers."""
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework.exceptions import ValidationError

from chats.serializers import ChatSerializer
from workspaces.models import Workspace

User = get_user_model()


class ChatSerializerTests(TestCase):
    """Тести валідації збережених чатів."""

    def setUp(self):
        """Створення користувача, workspace та mock-запиту."""
        self.user = User.objects.create_user(username='u1', password='pass')
        self.workspace = Workspace.objects.create(
            name='WS',
            model_names=['llama3'],
        )
        self.workspace.users.add(self.user)
        self.factory = RequestFactory()

    def _serializer(self, data, user=None):
        """Допоміжний метод для створення serializer з request context."""
        request = self.factory.post('/')
        request.user = user or self.user
        return ChatSerializer(data=data, context={'request': request})

    def test_valid_chat_data(self):
        """Коректні дані чату проходять валідацію."""
        serializer = self._serializer({
            'title': 'Test',
            'model': 'llama3',
            'workspace': self.workspace.pk,
            'messages': [{'role': 'user', 'content': 'Hi'}],
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_invalid_message_role(self):
        """Некоректна роль у messages відхиляється."""
        serializer = self._serializer({
            'title': 'Test',
            'model': 'llama3',
            'workspace': self.workspace.pk,
            'messages': [{'role': 'system', 'content': 'Hi'}],
        })
        self.assertFalse(serializer.is_valid())

    def test_requires_workspace_for_regular_user(self):
        """Звичайний користувач не може зберегти чат без workspace."""
        serializer = self._serializer({
            'title': 'Test',
            'model': 'llama3',
            'messages': [],
        })
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)
