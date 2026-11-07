"""Аналіз таблиці Chats Info локальною моделлю."""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from chats.models import WorkspaceChatLog
from chats.table_analysis import parse_model_analysis, pick_chat_model
from llm.admission import OllamaBusy
from llm.base import LLMProviderError
from workspaces.models import Workspace

User = get_user_model()


class TableAnalysisParseTests(APITestCase):
    """Розбір відповіді моделі без виклику Ollama."""

    def test_pick_prefers_gemma3(self):
        name = pick_chat_model([
            {'name': 'ayushshah/qwen3-1.7b-chat:q4_k_m'},
            {'name': 'gemma3:latest'},
        ])
        self.assertEqual(name, 'gemma3:latest')

    def test_pick_skips_embedding_model(self):
        name = pick_chat_model([
            {'name': 'nomic-embed-text:latest'},
            {'name': 'gemma3:latest'},
        ])
        self.assertEqual(name, 'gemma3:latest')

    def test_parse_fenced_json(self):
        parsed = parse_model_analysis(
            '```json\n{"summary":"Коротко","topics":[{"title":"Сертифікат","detail":"Часто"}],'
            '"problems":["Немає матеріалу"],"recommendations":["Додати FAQ"]}\n```',
        )
        self.assertEqual(parsed['summary'], 'Коротко')
        self.assertEqual(parsed['topics'][0]['title'], 'Сертифікат')
        self.assertEqual(parsed['problems'], ['Немає матеріалу'])

    def test_parse_labeled_text(self):
        parsed = parse_model_analysis(
            'Висновок: Питають про сертифікат.\n'
            'Теми: Сертифікат — як його отримати\n'
            'Проблеми: Мало оцінок\n'
            'Рекомендації: Додати FAQ\n',
        )
        self.assertEqual(parsed['summary'], 'Питають про сертифікат.')
        self.assertEqual(parsed['topics'][0]['title'], 'Сертифікат')
        self.assertEqual(parsed['topics'][0]['detail'], 'як його отримати')
        self.assertEqual(parsed['recommendations'], ['Додати FAQ'])

    def test_echoed_table_json_is_not_the_summary(self):
        parsed = parse_model_analysis('{"total": 11, "rows": []}')
        self.assertEqual(parsed['summary'], '')

    def test_parse_plain_text_becomes_summary(self):
        parsed = parse_model_analysis('Студенти питають про реєстрацію.')
        self.assertIn('реєстрацію', parsed['summary'])
        self.assertEqual(parsed['topics'], [])


class WorkspaceChatLogAnalysisApiTests(APITestCase):
    """POST /api/chats/logs/analysis/ лише для admin."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            password='pass',
            is_staff=True,
        )
        self.user = User.objects.create_user(username='user', password='pass')
        self.workspace = Workspace.objects.create(name='support', model_names=['llama3'])
        WorkspaceChatLog.objects.create(
            sent_by='student',
            workspace=self.workspace,
            prompt='Як отримати сертифікат?',
            response='У розділі Прогрес',
            feedback='up',
        )
        self.url = reverse('workspace_chat_logs_analysis')

    def test_requires_admin(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_empty_table_does_not_call_model(self):
        WorkspaceChatLog.objects.all().delete()
        self.client.force_authenticate(user=self.admin)
        with patch('chats.log_views.OllamaProvider') as provider_cls:
            response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 0)
        provider_cls.assert_not_called()

    @patch('chats.log_views.release_ollama_slot')
    @patch('chats.log_views.acquire_ollama_slot', return_value='token-1')
    @patch('chats.log_views.OllamaProvider')
    def test_returns_dashboard_from_local_model(self, provider_cls, _acquire, release):
        provider = MagicMock()
        provider.list_models.return_value = {'models': [{'name': 'qwen3:latest'}]}
        provider.chat.return_value = {
            'message': {
                'content': '{"summary":"Багато питань про сертифікат","topics":[],"problems":[],"recommendations":[]}',
            },
        }
        provider_cls.return_value = provider
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['model'], 'qwen3:latest')
        self.assertEqual(response.data['total'], 1)
        self.assertIn('сертифікат', response.data['summary'])
        provider.chat.assert_called_once()
        self.assertEqual(provider.chat.call_args.kwargs['options']['num_ctx'], 2048)
        release.assert_called_once_with('token-1')

    @patch('chats.log_views.acquire_ollama_slot', side_effect=OllamaBusy)
    @patch('chats.log_views.OllamaProvider')
    def test_busy_model_is_429(self, provider_cls, _acquire):
        provider_cls.return_value.list_models.return_value = {
            'models': [{'name': 'qwen3:latest'}],
        }
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['code'], 'ollama_busy')
        provider_cls.return_value.chat.assert_not_called()

    @patch('chats.log_views.release_ollama_slot')
    @patch('chats.log_views.acquire_ollama_slot', return_value='token-1')
    @patch('chats.log_views.OllamaProvider')
    def test_provider_error_is_503_and_releases_slot(self, provider_cls, _acquire, release):
        provider = MagicMock()
        provider.list_models.return_value = {'models': [{'name': 'qwen3:latest'}]}
        provider.chat.side_effect = LLMProviderError('down')
        provider_cls.return_value = provider
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        release.assert_called_once_with('token-1')
