"""Integration-тести для Chat API при недоступній інфраструктурі допуску (AdmissionUnavailable)."""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from llm.admission import AdmissionUnavailable
from workspaces.models import Workspace

User = get_user_model()


class ChatViewAdmissionFailureTests(APITestCase):
    """Перевірка fail-closed (HTTP 503) при AdmissionUnavailable."""

    def setUp(self):
        self.user = User.objects.create_user(username='chat_tester', password='pass')
        self.workspace = Workspace.objects.create(
            name='Chat Workspace',
            model_names=['llama3'],
        )
        self.workspace.users.add(self.user)
        self.client.force_authenticate(user=self.user)

    @patch('llm.chat.resolve_provider')
    @patch('llm.chat.prepare_chat_messages')
    @patch('llm.chat.acquire_ollama_slot', side_effect=AdmissionUnavailable('redis down'))
    def test_chat_view_returns_503_when_admission_unavailable(
        self, mock_acquire, mock_prepare, mock_resolve,
    ):
        mock_prepare.return_value = ([{'role': 'user', 'content': 'Привіт'}], [])
        provider = MagicMock()
        mock_resolve.return_value = provider

        response = self.client.post(
            '/api/ollama/chat/',
            {
                'model': 'llama3',
                'messages': [{'role': 'user', 'content': 'Привіт'}],
                'stream': False,
                'workspace_id': self.workspace.pk,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(
            response.data['error'],
            'Сервіс тимчасово недоступний. Спробуйте пізніше.',
        )
        provider.chat.assert_not_called()
