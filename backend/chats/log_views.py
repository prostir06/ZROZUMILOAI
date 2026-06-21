"""Admin API for workspace chat logs (Chats Info dashboard)."""
import logging

from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .export_service import (
    build_export_response,
    build_export_timestamp,
    parse_export_format,
    serialize_logs,
)
from .models import WorkspaceChatLog
from .serializers import WorkspaceChatLogSerializer

logger = logging.getLogger(__name__)


class WorkspaceChatLogListView(APIView):
    """Список записаних чатів workspace (лише admin)."""

    permission_classes = (IsAdminUser,)

    def get(self, request):
        try:
            logs = WorkspaceChatLog.objects.select_related('workspace', 'user')
            serializer = WorkspaceChatLogSerializer(logs, many=True)
            return Response(serializer.data)
        except Exception as exc:
            logger.exception('Помилка отримання списку chat logs: %s', exc)
            return Response(
                {'error': 'Не вдалося завантажити записи чатів'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class WorkspaceChatLogDetailView(APIView):
    """Видалити один запис Chats Info (лише admin)."""

    permission_classes = (IsAdminUser,)

    def delete(self, request, log_id):
        try:
            deleted, _ = WorkspaceChatLog.objects.filter(pk=log_id).delete()
        except Exception as exc:
            logger.exception('Помилка видалення chat log %s: %s', log_id, exc)
            return Response(
                {'error': 'Помилка видалення запису'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not deleted:
            return Response(
                {'error': 'Запис не знайдено'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({'deleted': log_id})


class WorkspaceChatLogClearView(APIView):
    """Очистити всі записи Chats Info (лише admin)."""

    permission_classes = (IsAdminUser,)

    def delete(self, request):
        try:
            deleted, _ = WorkspaceChatLog.objects.all().delete()
            return Response({'deleted': deleted})
        except Exception as exc:
            logger.exception('Помилка очищення chat logs: %s', exc)
            return Response(
                {'error': 'Помилка очищення записів'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class WorkspaceChatLogExportView(APIView):
    """Експорт записів Chats Info (лише admin)."""

    permission_classes = (IsAdminUser,)

    def get(self, request):
        export_format = parse_export_format(request)

        try:
            logs = WorkspaceChatLog.objects.select_related('workspace').order_by(
                '-created_at',
            )
            rows = serialize_logs(logs)
            timestamp = build_export_timestamp(logs)
            return build_export_response(rows, export_format, timestamp=timestamp)
        except ValueError as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception('Помилка експорту chat logs: %s', exc)
            return Response(
                {'error': 'Не вдалося виконати експорт'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
