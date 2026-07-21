"""Unit-тести фонового планувальника ingest."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from workspaces.rag.tasks import ingest_document_by_id, schedule_document_ingest


class ScheduleDocumentIngestTests(SimpleTestCase):
    """Перевірка планування через on_commit + Celery/thread fallback."""

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch('workspaces.rag.tasks._enqueue_celery', return_value=False)
    @patch('workspaces.rag.tasks.threading.Thread')
    @patch('workspaces.rag.tasks.transaction.on_commit')
    def test_schedule_falls_back_to_thread(
        self,
        mock_on_commit,
        mock_thread_cls,
        _mock_celery,
    ):
        schedule_document_ingest(42)
        mock_on_commit.assert_called_once()
        callback = mock_on_commit.call_args[0][0]
        callback()
        mock_thread_cls.assert_called_once()
        kwargs = mock_thread_cls.call_args.kwargs
        self.assertEqual(kwargs['args'], (42,))
        self.assertTrue(kwargs['daemon'])
        mock_thread_cls.return_value.start.assert_called_once()

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('workspaces.rag.tasks.ingest_document_task.delay')
    @patch('workspaces.rag.tasks.transaction.on_commit')
    def test_schedule_uses_celery_when_available(self, mock_on_commit, mock_delay):
        schedule_document_ingest(7)
        callback = mock_on_commit.call_args[0][0]
        callback()
        mock_delay.assert_called_once_with(7)


class IngestDocumentByIdTests(SimpleTestCase):
    """Тести синхронного ingest за id документа."""

    @patch('workspaces.rag.tasks.close_old_connections')
    def test_not_found(self, _mock_close):
        with patch('workspaces.models.WorkspaceDocument') as mock_model:
            mock_model.DoesNotExist = type('DoesNotExist', (Exception,), {})
            mock_model.objects.select_related.return_value.get.side_effect = (
                mock_model.DoesNotExist
            )
            result = ingest_document_by_id(999)
        self.assertEqual(result, {'ok': False, 'error': 'not_found'})

    @patch('workspaces.rag.tasks.close_old_connections')
    def test_ingest_success(self, _mock_close):
        document = MagicMock()
        with patch('workspaces.models.WorkspaceDocument') as mock_model:
            mock_model.DoesNotExist = type('DoesNotExist', (Exception,), {})
            mock_model.objects.select_related.return_value.get.return_value = (
                document
            )
            with patch(
                'workspaces.rag.service.ingest_workspace_document',
            ) as mock_ingest:
                result = ingest_document_by_id(5)
        mock_ingest.assert_called_once_with(document)
        self.assertTrue(result['ok'])
        self.assertEqual(result['document_id'], 5)

    @patch('workspaces.rag.tasks.close_old_connections')
    def test_ingest_exception_returns_error(self, _mock_close):
        document = MagicMock()
        with patch('workspaces.models.WorkspaceDocument') as mock_model:
            mock_model.DoesNotExist = type('DoesNotExist', (Exception,), {})
            mock_model.objects.select_related.return_value.get.return_value = (
                document
            )
            with patch(
                'workspaces.rag.service.ingest_workspace_document',
                side_effect=RuntimeError('boom'),
            ):
                result = ingest_document_by_id(5)
        self.assertFalse(result['ok'])
        self.assertIn('boom', result['error'])
