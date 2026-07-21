"""Unit-тести для workspace services."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from workspaces.models import Workspace
from workspaces.services import (
    get_allowed_model_names,
    get_gemini_api_key,
    get_ollama_options,
    prepare_chat_messages,
    resolve_workspace_for_chat,
    user_can_use_model,
)

User = get_user_model()


class WorkspaceServicesTests(TestCase):
    """Тести бізнес-логіки workspace."""

    def setUp(self):
        """Підготовка користувачів та workspace для тестів."""
        self.staff = User.objects.create_user(
            username='admin',
            password='pass',
            is_staff=True,
        )
        self.user = User.objects.create_user(
            username='user1',
            password='pass',
        )
        self.workspace = Workspace.objects.create(
            name='Support',
            system_prompt='Be helpful.',
            temperature=0.5,
            model_names=['llama3'],
        )
        self.workspace.users.add(self.user)

    def test_staff_sees_all_models(self):
        """Адміністратор має доступ до всіх моделей."""
        self.assertIsNone(get_allowed_model_names(self.staff))
        self.assertTrue(user_can_use_model(self.staff, 'any-model'))

    def test_user_limited_to_workspace_models(self):
        """Звичайний користувач обмежений моделями свого workspace."""
        allowed = get_allowed_model_names(self.user)
        self.assertEqual(allowed, {'llama3'})
        self.assertTrue(user_can_use_model(self.user, 'llama3'))
        self.assertFalse(user_can_use_model(self.user, 'mistral'))

    def test_resolve_workspace_requires_id_for_user(self):
        """Користувач без workspace_id отримує помилку валідації."""
        with self.assertRaises(ValidationError):
            resolve_workspace_for_chat(self.user, 'llama3')

    def test_resolve_workspace_validates_model(self):
        """Модель має належати обраному workspace."""
        with self.assertRaises(ValidationError):
            resolve_workspace_for_chat(
                self.user,
                'mistral',
                workspace_id=self.workspace.pk,
            )

    def test_prepare_chat_messages_injects_system_prompt(self):
        """System prompt workspace додається на початок повідомлень."""
        messages = [{'role': 'user', 'content': 'Hi'}]
        prepared, _sources = prepare_chat_messages(messages, self.workspace)
        self.assertEqual(prepared[0]['role'], 'system')
        self.assertEqual(prepared[0]['content'], 'Be helpful.')
        self.assertEqual(prepared[1]['content'], 'Hi')

    def test_prepare_chat_messages_injects_rag_context(self):
        """RAG-контекст додається до system prompt."""
        from unittest.mock import patch

        messages = [{'role': 'user', 'content': 'Що в FAQ?'}]
        fake_chunks = [{
            'content': 'Відповідь з FAQ',
            'score': 0.9,
            'document_name': 'faq.md',
        }]

        with patch(
            'workspaces.rag.service.search_workspace_context',
            return_value=fake_chunks,
        ):
            prepared, sources = prepare_chat_messages(
                messages,
                self.workspace,
                rag_query='Що в FAQ?',
            )

        self.assertEqual(prepared[0]['role'], 'system')
        self.assertIn('Be helpful.', prepared[0]['content'])
        self.assertIn('faq.md', prepared[0]['content'])
        self.assertIn('Відповідь з FAQ', prepared[0]['content'])
        self.assertEqual(sources[0]['document_name'], 'faq.md')

    def test_get_ollama_options_from_workspace(self):
        """Temperature workspace передається в Ollama options."""
        options = get_ollama_options(self.workspace)
        self.assertEqual(options, {'temperature': 0.5})

    def test_get_workspace_for_user_denies_foreign_workspace(self):
        """Користувач не має доступу до чужого workspace."""
        other = Workspace.objects.create(name='Other', model_names=['x'])
        with self.assertRaises(PermissionDenied):
            from workspaces.services import get_workspace_for_user
            get_workspace_for_user(self.user, other.pk)

    def test_get_gemini_api_key_prefers_workspace(self):
        """Ключ workspace має пріоритет над глобальним."""
        self.workspace.gemini_api_key = '  ws-key  '
        self.workspace.save()
        self.assertEqual(get_gemini_api_key(self.workspace), 'ws-key')

    @override_settings(GEMINI_API_KEY='global-key')
    def test_get_gemini_api_key_falls_back_to_settings(self):
        """Без ключа workspace використовується GEMINI_API_KEY."""
        self.assertEqual(get_gemini_api_key(self.workspace), 'global-key')
