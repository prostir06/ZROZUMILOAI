"""Unit-тести для WorkspaceSerializer."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from workspaces.models import Workspace
from workspaces.serializers import WorkspaceSerializer

User = get_user_model()


@override_settings(
    MEILISEARCH_URL='',
    MEILISEARCH_API_KEY='',
)
class WorkspaceSerializerTests(TestCase):
    """Валідація провайдера, Meilisearch та model_names."""

    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='pass')

    def test_rejects_gemini_provider(self):
        serializer = WorkspaceSerializer(data={
            'name': 'Local',
            'llm_provider': 'gemini',
            'model_names': ['llama3.2'],
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('llm_provider', serializer.errors)

    def test_rejects_gemini_api_key_even_when_blank(self):
        serializer = WorkspaceSerializer(data={
            'name': 'Local',
            'model_names': ['llama3.2'],
            'gemini_api_key': '',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('gemini_api_key', serializer.errors)

    def test_ollama_workspace_without_provider_is_valid(self):
        serializer = WorkspaceSerializer(data={
            'name': 'Local',
            'model_names': ['llama3.2'],
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

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
