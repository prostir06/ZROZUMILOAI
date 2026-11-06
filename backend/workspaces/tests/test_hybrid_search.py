"""Unit & integration tests for Hybrid Search (Full-Text & Reciprocal Rank Fusion)."""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from workspaces.models import DocumentChunk, Workspace, WorkspaceDocument
from workspaces.rag.fusion import reciprocal_rank_fusion
from workspaces.rag.search_context import search_workspace_documents
from workspaces.rag.text_search import search_with_fulltext


class HybridReciprocalRankFusionTests(TestCase):
    """Test RRF fusion when merging vector and full-text result sets."""

    def test_rrf_places_multihit_items_at_top(self):
        vector_results = [
            {
                'content': 'Вимоги стандарту ISO-9001 для контролю якості.',
                'document_name': 'iso.pdf',
                'score': 0.85,
            },
            {
                'content': 'Загальний посібник з менеджменту підприємства.',
                'document_name': 'management.pdf',
                'score': 0.80,
            },
        ]
        text_results = [
            {
                'content': 'Довідник термінів та скорочень.',
                'document_name': 'glossary.pdf',
                'score': 0.90,
            },
            {
                'content': 'Вимоги стандарту ISO-9001 для контролю якості.',
                'document_name': 'iso.pdf',
                'score': 0.95,
            },
        ]

        fused = reciprocal_rank_fusion([vector_results, text_results], top_k=3)

        self.assertEqual(len(fused), 3)
        # item present in both lists should be ranked #1
        self.assertEqual(
            fused[0]['content'],
            'Вимоги стандарту ISO-9001 для контролю якості.',
        )
        self.assertEqual(fused[0]['document_name'], 'iso.pdf')
        # max score preserved
        self.assertEqual(fused[0]['score'], 0.95)
        self.assertIn('rrf_score', fused[0])
        self.assertGreater(fused[0]['rrf_score'], fused[1]['rrf_score'])


class FulltextSearchTests(TestCase):
    """Test search_with_fulltext keyword matching and fallbacks."""

    def setUp(self):
        super().setUp()
        self.workspace = Workspace.objects.create(name='Fulltext WS')
        self.doc_ready = WorkspaceDocument.objects.create(
            workspace=self.workspace,
            original_filename='standards.txt',
            status=WorkspaceDocument.Status.READY,
        )
        self.doc_failed = WorkspaceDocument.objects.create(
            workspace=self.workspace,
            original_filename='failed.txt',
            status=WorkspaceDocument.Status.FAILED,
        )
        self.chunk_iso = DocumentChunk.objects.create(
            workspace=self.workspace,
            document=self.doc_ready,
            chunk_index=0,
            content='Сертифікація за міжнародним стандартом ISO-9001 гарантує якість.',
        )
        self.chunk_dstu = DocumentChunk.objects.create(
            workspace=self.workspace,
            document=self.doc_ready,
            chunk_index=1,
            content='Національний стандарт ДСТУ 1.0 встановлює правила стандартизації.',
        )
        self.chunk_failed = DocumentChunk.objects.create(
            workspace=self.workspace,
            document=self.doc_failed,
            chunk_index=0,
            content='Помилковий документ ISO-9001 не повинен знаходитися.',
        )

    def test_search_with_fulltext_finds_iso_9001(self):
        results = search_with_fulltext(self.workspace, 'ISO-9001', top_k=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.chunk_iso.pk)
        self.assertEqual(results[0]['chunk_index'], 0)
        self.assertEqual(results[0]['document_name'], 'standards.txt')
        self.assertGreater(results[0]['score'], 0.0)
        self.assertIn('ISO-9001', results[0]['content'])

    def test_search_with_fulltext_finds_dstu(self):
        # Case insensitive test for Cyrillic query
        results_upper = search_with_fulltext(self.workspace, 'ДСТУ', top_k=5)
        self.assertEqual(len(results_upper), 1)
        self.assertEqual(results_upper[0]['id'], self.chunk_dstu.pk)
        self.assertEqual(results_upper[0]['chunk_index'], 1)
        self.assertEqual(results_upper[0]['document_name'], 'standards.txt')
        self.assertGreater(results_upper[0]['score'], 0.0)
        self.assertIn('ДСТУ', results_upper[0]['content'])

        results_lower = search_with_fulltext(self.workspace, 'дсту', top_k=5)
        self.assertEqual(len(results_lower), 1)
        self.assertEqual(results_lower[0]['id'], self.chunk_dstu.pk)

    def test_search_with_fulltext_empty_query_or_no_match(self):
        self.assertEqual(search_with_fulltext(self.workspace, '', top_k=5), [])
        self.assertEqual(search_with_fulltext(self.workspace, '   ', top_k=5), [])
        self.assertEqual(
            search_with_fulltext(self.workspace, 'невідомеслово123', top_k=5),
            [],
        )

    def test_search_with_fulltext_ignores_non_ready_document(self):
        results = search_with_fulltext(self.workspace, 'ISO-9001', top_k=5)
        ids = [r['id'] for r in results]
        self.assertNotIn(self.chunk_failed.pk, ids)

    @patch('workspaces.rag.text_search.connection')
    @patch('workspaces.rag.text_search.DocumentChunk')
    def test_search_with_fulltext_postgresql_path(self, mock_chunk_cls, mock_conn):
        mock_conn.vendor = 'postgresql'
        chunk = MagicMock()
        chunk.pk = 42
        chunk.chunk_index = 2
        chunk.content = 'Postgres chunk content'
        chunk.document.original_filename = 'pg.pdf'
        chunk.rank = 0.75

        queryset = MagicMock()
        mock_qs = (
            queryset.annotate.return_value
            .filter.return_value
            .order_by.return_value
            .select_related.return_value
        )
        mock_qs.__getitem__.return_value = [chunk]
        mock_chunk_cls.objects.filter.return_value = queryset

        results = search_with_fulltext(self.workspace, 'query', top_k=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], 42)
        self.assertEqual(results[0]['score'], 0.75)
        self.assertEqual(results[0]['document_name'], 'pg.pdf')


class HybridSearchWorkspaceDocumentsTests(TestCase):
    """Test search_workspace_documents fusing vector and fulltext."""

    def setUp(self):
        super().setUp()
        self.workspace = Workspace.objects.create(name='Hybrid WS')

    @override_settings(RAG_ENABLED=True, RAG_TOP_K=5)
    @patch('workspaces.rag.search_context.search_with_fulltext')
    @patch('workspaces.rag.search_context.search_with_python')
    @patch('workspaces.rag.search_context.uses_pgvector', return_value=False)
    @patch('workspaces.rag.search_context.cached_query_embedding')
    def test_both_vector_and_text_succeed_fuses_results(
        self,
        mock_embed,
        _mock_pg,
        mock_python,
        mock_fulltext,
    ):
        mock_embed.return_value = [0.1, 0.2]
        mock_python.return_value = [
            {'content': 'Chunk A', 'document_name': 'a.pdf', 'score': 0.8},
            {'content': 'Chunk B', 'document_name': 'b.pdf', 'score': 0.7},
        ]
        mock_fulltext.return_value = [
            {
                'content': 'Chunk C',
                'document_name': 'c.pdf',
                'score': 0.9,
                'id': 3,
                'chunk_index': 0,
            },
            {
                'content': 'Chunk A',
                'document_name': 'a.pdf',
                'score': 0.95,
                'id': 1,
                'chunk_index': 0,
            },
        ]

        results = search_workspace_documents(self.workspace, 'test query', top_k=3)

        mock_python.assert_called_once()
        mock_fulltext.assert_called_once_with(self.workspace, 'test query', top_k=3)
        self.assertEqual(len(results), 3)
        # Multi-hit item A should be ranked #1
        self.assertEqual(results[0]['content'], 'Chunk A')
        self.assertEqual(results[0]['score'], 0.95)

    @override_settings(RAG_ENABLED=True, RAG_TOP_K=5)
    @patch('workspaces.rag.search_context.search_with_fulltext')
    @patch('workspaces.rag.search_context.search_with_python')
    @patch('workspaces.rag.search_context.uses_pgvector', return_value=False)
    @patch('workspaces.rag.search_context.cached_query_embedding')
    def test_vector_only_succeeds(
        self,
        mock_embed,
        _mock_pg,
        mock_python,
        mock_fulltext,
    ):
        mock_embed.return_value = [0.1, 0.2]
        mock_python.return_value = [
            {'content': 'Vector Chunk', 'document_name': 'vec.pdf', 'score': 0.85},
        ]
        mock_fulltext.return_value = []

        results = search_workspace_documents(self.workspace, 'vector test', top_k=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['content'], 'Vector Chunk')

    @override_settings(RAG_ENABLED=True, RAG_TOP_K=5)
    @patch('workspaces.rag.search_context.search_with_fulltext')
    @patch('workspaces.rag.search_context.cached_query_embedding')
    def test_embedding_fails_resilient_fallback_to_fulltext(
        self,
        mock_embed,
        mock_fulltext,
    ):
        """When embedding fails/raises, fulltext search still runs and returns results."""
        mock_embed.side_effect = RuntimeError('Ollama timeout')
        mock_fulltext.return_value = [
            {
                'content': 'Fulltext Chunk',
                'document_name': 'text.pdf',
                'score': 0.9,
                'id': 10,
                'chunk_index': 0,
            },
        ]

        results = search_workspace_documents(self.workspace, 'resilience query', top_k=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['content'], 'Fulltext Chunk')
        mock_fulltext.assert_called_once_with(self.workspace, 'resilience query', top_k=5)

    @override_settings(RAG_ENABLED=True, RAG_TOP_K=5)
    @patch('workspaces.rag.search_context.search_with_fulltext', return_value=[])
    @patch('workspaces.rag.search_context.cached_query_embedding', side_effect=Exception('fail'))
    def test_neither_succeeds_returns_empty(self, _mock_embed, _mock_fulltext):
        results = search_workspace_documents(self.workspace, 'none', top_k=5)
        self.assertEqual(results, [])
