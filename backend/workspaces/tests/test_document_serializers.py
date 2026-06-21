"""Unit-тести document serializers."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from workspaces.document_serializers import WorkspaceDocumentUploadSerializer


class WorkspaceDocumentUploadSerializerTests(SimpleTestCase):
    @override_settings(RAG_MAX_FILE_SIZE=1024)
    def test_rejects_large_file(self):
        uploaded = SimpleUploadedFile('big.txt', b'x' * 2048)
        serializer = WorkspaceDocumentUploadSerializer(data={'file': uploaded})
        self.assertFalse(serializer.is_valid())
        self.assertIn('file', serializer.errors)

    def test_rejects_unsupported_extension(self):
        uploaded = SimpleUploadedFile('virus.exe', b'data')
        serializer = WorkspaceDocumentUploadSerializer(data={'file': uploaded})
        self.assertFalse(serializer.is_valid())

    def test_accepts_txt_file(self):
        uploaded = SimpleUploadedFile('note.txt', b'hello', content_type='text/plain')
        serializer = WorkspaceDocumentUploadSerializer(data={'file': uploaded})
        self.assertTrue(serializer.is_valid(), serializer.errors)
