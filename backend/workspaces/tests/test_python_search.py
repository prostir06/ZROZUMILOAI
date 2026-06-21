"""Unit-тести Python fallback RAG-пошуку."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from workspaces.rag.python_search import search_with_python


class PythonSearchTests(SimpleTestCase):
    @patch('workspaces.rag.python_search.DocumentChunk')
    def test_empty_chunks(self, mock_chunk_model):
        queryset = MagicMock()
        queryset.exists.return_value = False
        mock_chunk_model.objects.filter.return_value.select_related.return_value = queryset

        self.assertEqual(search_with_python(MagicMock(), [1.0], 3), [])

    @patch('workspaces.rag.python_search.cosine_similarity', return_value=0.8)
    @patch('workspaces.rag.python_search.DocumentChunk')
    def test_returns_scored_chunk(self, mock_chunk_model, _mock_sim):
        chunk = MagicMock()
        chunk.pk = 1
        chunk.embedding = [0.5, 0.5]
        chunk.content = 'контент'
        chunk.document.original_filename = 'doc.txt'

        queryset = MagicMock()
        queryset.exists.return_value = True
        queryset.iterator.return_value = [chunk]
        mock_chunk_model.objects.filter.return_value.select_related.return_value = queryset

        results = search_with_python(MagicMock(), [1.0, 0.0], top_k=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['document_name'], 'doc.txt')
