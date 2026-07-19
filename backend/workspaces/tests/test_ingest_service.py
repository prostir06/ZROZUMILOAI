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

    @patch('workspaces.rag.service.OllamaService')
    @patch(
        'workspaces.rag.service.extract_text_from_file',
        return_value='Короткий FAQ текст для індексації.',
    )
    def test_ingest_creates_chunks_and_marks_ready(self, _extract, mock_ollama_cls):
        mock_ollama_cls.return_value.embed.return_value = [0.1, 0.2, 0.3]

        ingest_workspace_document(self.document)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, WorkspaceDocument.Status.READY)
        self.assertGreaterEqual(self.document.chunk_count, 1)
        self.assertEqual(
            DocumentChunk.objects.filter(document=self.document).count(),
            self.document.chunk_count,
        )
        mock_ollama_cls.return_value.embed.assert_called()

    @patch('workspaces.rag.service.OllamaService')
    @patch(
        'workspaces.rag.service.extract_text_from_file',
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
