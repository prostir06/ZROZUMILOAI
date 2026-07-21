"""API-тести документів workspace: upload schedule, retry, rag-stats."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from workspaces.models import Workspace, WorkspaceDocument

User = get_user_model()


class WorkspaceDocumentApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin_docs',
            email='admin@example.com',
            password='pass',
        )
        self.user = User.objects.create_user(username='user_docs', password='pass')
        self.workspace = Workspace.objects.create(
            name='Docs WS',
            model_names=['llama3'],
        )
        self.client = APIClient()

    @patch('workspaces.document_views.schedule_document_ingest')
    def test_upload_schedules_ingest(self, mock_schedule):
        self.client.force_authenticate(user=self.admin)
        uploaded = SimpleUploadedFile(
            'faq.txt',
            b'Hello RAG document',
            content_type='text/plain',
        )
        response = self.client.post(
            f'/api/workspaces/{self.workspace.pk}/documents/',
            {'file': uploaded},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'processing')
        mock_schedule.assert_called_once()

    @patch(
        'workspaces.document_views.schedule_document_ingest',
        side_effect=RuntimeError('broker down'),
    )
    def test_upload_marks_failed_when_schedule_raises(self, _mock_schedule):
        self.client.force_authenticate(user=self.admin)
        uploaded = SimpleUploadedFile(
            'faq.txt',
            b'Hello',
            content_type='text/plain',
        )
        response = self.client.post(
            f'/api/workspaces/{self.workspace.pk}/documents/',
            {'file': uploaded},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'failed')
        self.assertIn('індексацію', response.data['error_message'])

    @patch('workspaces.document_views.schedule_document_ingest')
    def test_reindex_failed_documents(self, mock_schedule):
        self.client.force_authenticate(user=self.admin)
        doc = WorkspaceDocument.objects.create(
            workspace=self.workspace,
            original_filename='fail.txt',
            file=SimpleUploadedFile('fail.txt', b'data'),
            file_size=4,
            status=WorkspaceDocument.Status.FAILED,
            error_message='boom',
        )
        response = self.client.post(
            f'/api/workspaces/{self.workspace.pk}/rag-stats/',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertIn(doc.pk, response.data['queued'])
        mock_schedule.assert_called_once_with(doc.pk)

    def test_upload_forbidden_for_non_admin(self):
        self.client.force_authenticate(user=self.user)
        uploaded = SimpleUploadedFile('faq.txt', b'x', content_type='text/plain')
        response = self.client.post(
            f'/api/workspaces/{self.workspace.pk}/documents/',
            {'file': uploaded},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('workspaces.document_views.schedule_document_ingest')
    def test_retry_failed_document(self, mock_schedule):
        self.client.force_authenticate(user=self.admin)
        document = WorkspaceDocument.objects.create(
            workspace=self.workspace,
            original_filename='fail.txt',
            file=SimpleUploadedFile('fail.txt', b'data'),
            file_size=4,
            status=WorkspaceDocument.Status.FAILED,
            error_message='boom',
        )
        response = self.client.post(
            f'/api/workspaces/{self.workspace.pk}/documents/{document.pk}/retry/',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        document.refresh_from_db()
        self.assertEqual(document.status, WorkspaceDocument.Status.PROCESSING)
        mock_schedule.assert_called_once_with(document.pk)

    def test_rag_stats(self):
        self.client.force_authenticate(user=self.admin)
        WorkspaceDocument.objects.create(
            workspace=self.workspace,
            original_filename='ok.txt',
            file=SimpleUploadedFile('ok.txt', b'data'),
            file_size=4,
            status=WorkspaceDocument.Status.READY,
            chunk_count=3,
        )
        response = self.client.get(
            f'/api/workspaces/{self.workspace.pk}/rag-stats/',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['documents_ready'], 1)
        self.assertEqual(response.data['chunks_total'], 3)
