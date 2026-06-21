"""API для документів workspace (RAG)."""
import logging

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .document_serializers import (
    WorkspaceDocumentSerializer,
    WorkspaceDocumentUploadSerializer,
)
from .models import Workspace, WorkspaceDocument
from .rag.service import ingest_workspace_document, sanitize_filename

logger = logging.getLogger(__name__)


class WorkspaceDocumentListCreateView(APIView):
    """Список або завантаження документів workspace (admin)."""

    permission_classes = (IsAdminUser,)
    parser_classes = (MultiPartParser, FormParser)

    def get(self, request, workspace_id):
        try:
            workspace = self._get_workspace(workspace_id)
            documents = workspace.documents.all()
            serializer = WorkspaceDocumentSerializer(documents, many=True)
            return Response(serializer.data)
        except NotFound:
            raise
        except Exception as exc:
            logger.error('List documents failed: %s', exc)
            return Response(
                {'error': 'Не вдалося отримати список документів'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request, workspace_id):
        workspace = self._get_workspace(workspace_id)
        serializer = WorkspaceDocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded = serializer.validated_data['file']
        document = WorkspaceDocument.objects.create(
            workspace=workspace,
            original_filename=sanitize_filename(uploaded.name),
            file=uploaded,
            file_size=uploaded.size,
            status=WorkspaceDocument.Status.PROCESSING,
        )

        try:
            ingest_workspace_document(document)
        except Exception as exc:
            logger.error('Document ingest error: %s', exc)
            document.refresh_from_db()
            if document.status != WorkspaceDocument.Status.FAILED:
                document.status = WorkspaceDocument.Status.FAILED
                document.error_message = str(exc)[:2000]
                document.save(update_fields=['status', 'error_message', 'updated_at'])

        document.refresh_from_db()
        return Response(
            WorkspaceDocumentSerializer(document).data,
            status=status.HTTP_201_CREATED,
        )

    def _get_workspace(self, workspace_id):
        try:
            return Workspace.objects.get(pk=workspace_id)
        except Workspace.DoesNotExist as exc:
            raise NotFound('Workspace не знайдено') from exc


class WorkspaceDocumentDeleteView(APIView):
    """Видалити документ workspace (admin)."""

    permission_classes = (IsAdminUser,)

    def delete(self, request, workspace_id, document_id):
        try:
            document = WorkspaceDocument.objects.get(
                pk=document_id,
                workspace_id=workspace_id,
            )
        except WorkspaceDocument.DoesNotExist:
            return Response(
                {'error': 'Документ не знайдено'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if document.file:
            try:
                document.file.delete(save=False)
            except OSError as exc:
                logger.warning('Could not delete file for document %s: %s', document_id, exc)

        document.delete()
        return Response({'deleted': document_id})
