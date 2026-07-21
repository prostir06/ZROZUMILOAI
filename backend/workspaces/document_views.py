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
from .rag.service import sanitize_filename, workspace_rag_stats
from .rag.tasks import schedule_document_ingest

logger = logging.getLogger(__name__)


def _mark_schedule_failed(document, exc):
    """Позначити документ FAILED, якщо не вдалося поставити ingest у чергу."""
    document.status = WorkspaceDocument.Status.FAILED
    document.error_message = f'Не вдалося запустити індексацію: {exc}'[:2000]
    try:
        document.save(update_fields=['status', 'error_message', 'updated_at'])
    except Exception as save_exc:
        logger.exception(
            'Failed to persist schedule error for document %s: %s',
            document.pk,
            save_exc,
        )


def _queue_document_ingest(document):
    """
    Поставити документ у чергу Celery/thread.

    :return: True якщо enqueue успішний.
    """
    try:
        schedule_document_ingest(document.pk)
        return True
    except Exception as exc:
        logger.exception('Failed to schedule ingest for %s: %s', document.pk, exc)
        _mark_schedule_failed(document, exc)
        return False


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
        try:
            document = WorkspaceDocument.objects.create(
                workspace=workspace,
                original_filename=sanitize_filename(uploaded.name),
                file=uploaded,
                file_size=uploaded.size,
                status=WorkspaceDocument.Status.PROCESSING,
            )
        except Exception as exc:
            logger.exception('Document create failed: %s', exc)
            return Response(
                {'error': 'Не вдалося зберегти файл документа'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        _queue_document_ingest(document)
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
                logger.warning(
                    'Could not delete file for document %s: %s',
                    document_id,
                    exc,
                )

        try:
            document.delete()
        except Exception as exc:
            logger.exception('Document delete failed for %s: %s', document_id, exc)
            return Response(
                {'error': 'Не вдалося видалити документ'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response({'deleted': document_id})


class WorkspaceDocumentRetryView(APIView):
    """
    Повторна індексація failed документа.

    Статус стає PROCESSING одразу; фактичний ingest виконує Celery/worker.
    """

    permission_classes = (IsAdminUser,)

    def post(self, request, workspace_id, document_id):
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

        try:
            document.status = WorkspaceDocument.Status.PROCESSING
            document.error_message = ''
            document.save(update_fields=['status', 'error_message', 'updated_at'])
        except Exception as exc:
            logger.exception('Retry status update failed for %s: %s', document_id, exc)
            return Response(
                {'error': 'Не вдалося оновити статус документа'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        _queue_document_ingest(document)
        document.refresh_from_db()
        return Response(WorkspaceDocumentSerializer(document).data)


class WorkspaceRagStatsView(APIView):
    """Статистика RAG + масовий reindex failed документів."""

    permission_classes = (IsAdminUser,)

    def get(self, request, workspace_id):
        try:
            workspace = Workspace.objects.get(pk=workspace_id)
        except Workspace.DoesNotExist:
            return Response(
                {'error': 'Workspace не знайдено'},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            return Response(workspace_rag_stats(workspace))
        except Exception as exc:
            logger.exception('RAG stats failed for workspace %s: %s', workspace_id, exc)
            return Response(
                {'error': 'Не вдалося отримати статистику RAG'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request, workspace_id):
        """Поставити всі failed документи у чергу повторно (по одному, fail-isolated)."""
        try:
            workspace = Workspace.objects.get(pk=workspace_id)
        except Workspace.DoesNotExist:
            return Response(
                {'error': 'Workspace не знайдено'},
                status=status.HTTP_404_NOT_FOUND,
            )

        failed = list(
            workspace.documents.filter(status=WorkspaceDocument.Status.FAILED),
        )
        queued = []
        for document in failed:
            try:
                document.status = WorkspaceDocument.Status.PROCESSING
                document.error_message = ''
                document.save(
                    update_fields=['status', 'error_message', 'updated_at'],
                )
                if _queue_document_ingest(document):
                    queued.append(document.pk)
            except Exception as exc:
                logger.exception(
                    'Reindex skipped for document %s: %s',
                    document.pk,
                    exc,
                )

        try:
            stats = workspace_rag_stats(workspace)
        except Exception as exc:
            logger.exception('RAG stats after reindex failed: %s', exc)
            stats = {}

        return Response({
            'queued': queued,
            'count': len(queued),
            'stats': stats,
        })
