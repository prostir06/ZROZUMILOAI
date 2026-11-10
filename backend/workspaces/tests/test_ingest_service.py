"""Unit-тести ingest_workspace_document (P0: embed поза atomic + bulk_create)."""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from workspaces.models import DocumentChunk, Workspace, WorkspaceDocument
from workspaces.rag.service import ingest_workspace_document


@override_settings(
    RAG_CHUNK_SIZE=800,
    RAG_CHUNK_OVERLAP=100,
    RAG_EMBED_MODEL='nomic-embed-text',
)
class IngestWorkspaceDocumentTests(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(
            name='RAG WS',
            model_names=['llama3'],
        )
        self.document = WorkspaceDocument.objects.create(
            workspace=self.workspace,
            original_filename='faq.md',
            file_size=10,
            status=WorkspaceDocument.Status.PROCESSING,
        )
        self.document.file = MagicMock()
        self.document.file.path = '/tmp/faq.md'

    @patch('workspaces.rag.ingest.OllamaService')
    @patch(
        'workspaces.rag.ingest.extract_text_from_file',
        return_value='Короткий FAQ текст для індексації.',
    )
    def test_ingest_creates_chunks_and_marks_ready(self, _extract, mock_ollama_cls):
        mock_ollama_cls.return_value.embed.return_value = [0.1] * 768

        ingest_workspace_document(self.document)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, WorkspaceDocument.Status.READY)
        self.assertGreaterEqual(self.document.chunk_count, 1)
        self.assertEqual(
            DocumentChunk.objects.filter(document=self.document).count(),
            self.document.chunk_count,
        )
        mock_ollama_cls.return_value.embed.assert_called()

    @patch('workspaces.rag.ingest.OllamaService')
    @patch(
        'workspaces.rag.ingest.extract_text_from_file',
        side_effect=ValueError('bad file'),
    )
    def test_ingest_marks_failed_on_error(self, _extract, mock_ollama_cls):
        with self.assertRaises(ValueError):
            ingest_workspace_document(self.document)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, WorkspaceDocument.Status.FAILED)
        self.assertIn('bad file', self.document.error_message)
        self.assertEqual(
            DocumentChunk.objects.filter(document=self.document).count(),
            0,
        )

    @patch('workspaces.rag.ingest.OllamaService')
    @patch(
        'workspaces.rag.ingest.extract_text_from_file',
        return_value='Текст для embeddings.',
    )
    def test_ingest_marks_failed_when_embed_raises(self, _extract, mock_ollama_cls):
        """Падіння Ollama embed → документ FAILED, без чанків."""
        import requests

        mock_ollama_cls.return_value.embed.side_effect = requests.RequestException(
            'ollama down',
        )
        with self.assertRaises(requests.RequestException):
            ingest_workspace_document(self.document)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, WorkspaceDocument.Status.FAILED)
        self.assertIn('ollama down', self.document.error_message)
        self.assertEqual(
            DocumentChunk.objects.filter(document=self.document).count(),
            0,
        )

    @override_settings(
        RAG_EMBED_BATCH_SIZE=2,
        RAG_EMBED_BATCH_PAUSE_SECONDS=0.0,
        OLLAMA_INGEST_SLOT_WAIT_SECONDS=5.0,
    )
    @patch('workspaces.rag.ingest.release_ollama_slot')
    @patch('workspaces.rag.ingest.acquire_ollama_slot', side_effect=['tok1', 'tok2'])
    @patch('workspaces.rag.ingest.OllamaService')
    @patch(
        'workspaces.rag.ingest.split_text_into_chunks',
        return_value=['c1', 'c2', 'c3'],
    )
    @patch(
        'workspaces.rag.ingest.extract_text_from_file',
        return_value='text',
    )
    def test_ingest_batches_chunks_and_acquires_slot_per_batch(
        self,
        _extract,
        _split,
        mock_ollama_cls,
        mock_acquire,
        mock_release,
    ):
        mock_ollama = mock_ollama_cls.return_value
        mock_ollama.embed_batch.side_effect = [
            [[0.1] * 768, [0.3] * 768],
            [[0.5] * 768],
        ]

        ingest_workspace_document(self.document)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, WorkspaceDocument.Status.READY)
        self.assertEqual(self.document.chunk_count, 3)
        self.assertEqual(mock_ollama.embed_batch.call_count, 2)
        self.assertEqual(mock_acquire.call_count, 2)
        self.assertEqual(
            [c.args[0] for c in mock_release.call_args_list],
            ['tok1', 'tok2'],
        )

