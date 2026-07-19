"""Unit-тести фонового планувальника ingest."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from workspaces.rag.tasks import schedule_document_ingest


class ScheduleDocumentIngestTests(SimpleTestCase):
    """Перевірка, що ingest планується через on_commit."""

    @patch('workspaces.rag.tasks.threading.Thread')
    @patch('workspaces.rag.tasks.transaction.on_commit')
    def test_schedule_registers_on_commit(self, mock_on_commit, mock_thread_cls):
        schedule_document_ingest(42)
        mock_on_commit.assert_called_once()
        callback = mock_on_commit.call_args[0][0]
        callback()
        mock_thread_cls.assert_called_once()
        kwargs = mock_thread_cls.call_args.kwargs
        self.assertEqual(kwargs['args'], (42,))
        self.assertTrue(kwargs['daemon'])
        mock_thread_cls.return_value.start.assert_called_once()
