"""API-тести Workspace CRUD та document upload path uniqueness."""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from workspaces.models import Workspace, workspace_document_upload_to
from workspaces.models import WorkspaceDocument

User = get_user_model()


class WorkspaceApiTests(APITestCase):
    """Admin CRUD для workspaces."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_ws',
            password='pass',
            is_staff=True,
        )
        self.user = User.objects.create_user(username='user_ws', password='pass')
        self.list_url = reverse('workspace_list_create')

    def test_list_requires_admin(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_creates_and_lists_workspace(self):
        self.client.force_authenticate(user=self.admin)
        create = self.client.post(
            self.list_url,
            {
                'name': 'Support',
                'model_names': ['llama3'],
                'temperature': 0.5,
                'user_ids': [],
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create.data['name'], 'Support')

        listed = self.client.get(self.list_url)
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(listed.data), 1)

    def test_admin_updates_and_deletes_workspace(self):
        workspace = Workspace.objects.create(
            name='Old',
            model_names=['llama3'],
        )
        self.client.force_authenticate(user=self.admin)
        detail = reverse('workspace_detail', kwargs={'workspace_id': workspace.pk})
        patched = self.client.patch(
            detail,
            {'name': 'New'},
            format='json',
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(patched.data['name'], 'New')

        deleted = self.client.delete(detail)
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Workspace.objects.filter(pk=workspace.pk).exists())


class DocumentUploadPathTests(APITestCase):
    """UUID-префікс у шляху файлу уникає overwrite."""

    def test_same_filename_gets_unique_storage_path(self):
        workspace = Workspace.objects.create(name='Docs', model_names=['llama3'])
        doc = WorkspaceDocument(workspace=workspace, original_filename='faq.txt')
        path_a = workspace_document_upload_to(doc, 'faq.txt')
        path_b = workspace_document_upload_to(doc, 'faq.txt')
        self.assertNotEqual(path_a, path_b)
        self.assertIn('faq.txt', path_a)
        self.assertIn(f'workspace_documents/{workspace.pk}/', path_a)
