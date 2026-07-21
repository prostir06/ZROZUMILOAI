"""Unit-тести RAG service helpers."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from workspaces.rag.service import (
    extract_last_user_message,
    format_rag_context,
    sanitize_filename,
    search_workspace_context,
    search_workspace_documents,
)


class RagServiceHelperTests(SimpleTestCase):
    def test_format_rag_context_empty(self):
        self.assertEqual(format_rag_context([]), '')

    def test_format_rag_context_includes_content(self):
        chunks = [{
            'content': 'Текст FAQ',
            'score': 0.9,
            'document_name': 'faq.md',
        }]
        context = format_rag_context(chunks)
        self.assertIn('faq.md', context)
        self.assertIn('Текст FAQ', context)

    def test_extract_last_user_message(self):
        messages = [
            {'role': 'user', 'content': 'Перше'},
            {'role': 'assistant', 'content': 'Відповідь'},
            {'role': 'user', 'content': '  Друге  '},
        ]
        self.assertEqual(extract_last_user_message(messages), 'Друге')

    def test_extract_last_user_message_invalid_input(self):
        self.assertIsNone(extract_last_user_message(None))
        self.assertIsNone(extract_last_user_message('text'))

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename('../../evil.pdf'), 'evil.pdf')
        self.assertTrue(sanitize_filename(''))

    @override_settings(RAG_ENABLED=False)
    def test_search_disabled_returns_empty(self):
        result = search_workspace_documents(MagicMock(), 'query')
        self.assertEqual(result, [])

    @override_settings(RAG_ENABLED=True, RAG_EMBED_MODEL='test', RAG_TOP_K=2)
    @patch('workspaces.rag.service.search_with_python')
    @patch('workspaces.rag.service.uses_pgvector', return_value=False)
    @patch('workspaces.rag.service.OllamaService')
    def test_search_delegates_to_python(self, mock_ollama, _mock_pg, mock_python):
        mock_ollama.return_value.embed.return_value = [0.1, 0.2]
        mock_python.return_value = [{'content': 'x', 'score': 1, 'document_name': 'a.txt'}]

        result = search_workspace_documents(MagicMock(), 'питання')

        mock_python.assert_called_once()
        self.assertEqual(len(result), 1)

    @override_settings(RAG_ENABLED=True, RAG_EMBED_MODEL='test', RAG_TOP_K=2)
    @patch('workspaces.rag.service.OllamaService')
    def test_search_returns_empty_on_embed_error(self, mock_ollama):
        mock_ollama.return_value.embed.side_effect = RuntimeError('ollama down')

        result = search_workspace_documents(MagicMock(), 'питання')
        self.assertEqual(result, [])


class SearchWorkspaceContextTests(SimpleTestCase):
    """Тести об'єднання internal RAG та Meilisearch."""

    def test_empty_query_returns_empty(self):
        workspace = MagicMock()
        self.assertEqual(search_workspace_context(workspace, ''), [])

    @override_settings(RAG_TOP_K=3)
    @patch('workspaces.rag.meilisearch_search.search_openedx_meilisearch')
    @patch('workspaces.rag.service.search_workspace_documents')
    def test_hybrid_merges_and_sorts(self, mock_internal, mock_meili):
        """HYBRID об'єднує результати через RRF (обидва джерела в топі)."""
        workspace = MagicMock()
        workspace.search_source = 'hybrid'

        mock_internal.return_value = [{
            'content': 'local',
            'score': 0.5,
            'document_name': 'doc.txt',
        }]
        mock_meili.return_value = [{
            'content': 'edx',
            'score': 0.9,
            'document_name': 'Course',
        }]

        result = search_workspace_context(workspace, 'query')

        self.assertEqual(len(result), 2)
        contents = {item['content'] for item in result}
        self.assertEqual(contents, {'local', 'edx'})
        mock_internal.assert_called_once()
        mock_meili.assert_called_once()

    @override_settings(RAG_TOP_K=2)
    @patch('workspaces.rag.service.search_workspace_documents')
    def test_internal_only_skips_meilisearch(self, mock_internal):
        """INTERNAL викликає лише локальний RAG."""
        workspace = MagicMock()
        workspace.search_source = 'internal'
        mock_internal.return_value = []

        with patch(
            'workspaces.rag.meilisearch_search.search_openedx_meilisearch',
        ) as mock_meili:
            search_workspace_context(workspace, 'query')
            mock_meili.assert_not_called()
