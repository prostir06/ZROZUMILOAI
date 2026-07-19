"""Unit-тести для WorkspaceSerializer."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from workspaces.models import Workspace
from workspaces.serializers import WorkspaceSerializer

User = get_user_model()


@override_settings(
    GEMINI_API_KEY='',
    GEMINI_MODEL_NAMES=['gemini-2.0-flash'],
    MEILISEARCH_URL='',
    MEILISEARCH_API_KEY='',
)
class WorkspaceSerializerTests(TestCase):
    """Валідація Gemini, Meilisearch та model_names."""

    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='pass')

    def test_gemini_requires_api_key_with_model(self):
        """Gemini провайдер без ключа відхиляється при виборі моделі."""
        serializer = WorkspaceSerializer(data={
            'name': 'Gemini WS',
            'llm_provider': Workspace.LLMProvider.GEMINI,
            'model_names': ['gemini-2.0-flash'],
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('gemini_api_key', serializer.errors)

    def test_gemini_accepts_workspace_key(self):
        """Ключ у payload проходить валідацію."""
        serializer = WorkspaceSerializer(data={
            'name': 'Gemini WS',
            'llm_provider': Workspace.LLMProvider.GEMINI,
            'model_names': ['gemini-2.0-flash'],
            'gemini_api_key': 'secret-key',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_gemini_rejects_non_gemini_model(self):
        """Для Gemini дозволені лише моделі з GEMINI_MODEL_NAMES."""
        serializer = WorkspaceSerializer(data={
            'name': 'Bad model',
            'llm_provider': Workspace.LLMProvider.GEMINI,
            'model_names': ['llama3'],
            'gemini_api_key': 'secret-key',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('model_names', serializer.errors)

    def test_single_model_limit(self):
        """Workspace приймає лише одну модель."""
        serializer = WorkspaceSerializer(data={
            'name': 'Multi',
            'model_names': ['llama3', 'mistral'],
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('model_names', serializer.errors)

    def test_meilisearch_requires_url(self):
        """Meilisearch search_source вимагає URL."""
        serializer = WorkspaceSerializer(data={
            'name': 'MS',
            'search_source': Workspace.SearchSource.MEILISEARCH,
            'meilisearch_api_key': 'key',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('meilisearch_url', serializer.errors)

    def test_meilisearch_requires_api_key(self):
        """Meilisearch search_source вимагає API key."""
        serializer = WorkspaceSerializer(data={
            'name': 'MS',
            'search_source': Workspace.SearchSource.MEILISEARCH,
            'meilisearch_url': 'http://meili.local',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('meilisearch_api_key', serializer.errors)

    @override_settings(
        MEILISEARCH_URL='http://meili.local',
        MEILISEARCH_API_KEY='global-key',
    )
    def test_meilisearch_uses_global_settings(self):
        """Глобальні MEILISEARCH_* з .env задовольняють валідацію."""
        serializer = WorkspaceSerializer(data={
            'name': 'MS global',
            'search_source': Workspace.SearchSource.HYBRID,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_create_workspace_with_users(self):
        """create зберігає workspace і прив'язує користувачів."""
        serializer = WorkspaceSerializer(data={
            'name': 'Support',
            'model_names': ['llama3'],
            'user_ids': [self.user.pk],
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        workspace = serializer.save()
        self.assertEqual(workspace.users.count(), 1)
