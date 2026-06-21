"""Unit-тести pgvector RAG-пошуку."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from workspaces.rag.vector_search import search_with_pgvector, uses_pgvector


class PgvectorSearchTests(SimpleTestCase):
    @override_settings(DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3'}})
    def test_uses_pgvector_false_on_sqlite(self):
        self.assertFalse(uses_pgvector())

    @patch('workspaces.rag.vector_search.DocumentChunk')
    def test_search_with_pgvector_returns_scored_results(self, mock_chunk_model):
        chunk = MagicMock()
        chunk.content = 'FAQ текст'
        chunk.distance = 0.2
        chunk.document.original_filename = 'faq.md'

        queryset = MagicMock()
        queryset.annotate.return_value = queryset
        queryset.order_by.return_value = queryset
        queryset.select_related.return_value = queryset
        queryset.__getitem__.return_value = [chunk]
        mock_chunk_model.objects.filter.return_value = queryset

        results = search_with_pgvector(workspace=MagicMock(), query_vector=[0.1] * 768, top_k=3)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['content'], 'FAQ текст')
        self.assertAlmostEqual(results[0]['score'], 0.8)
