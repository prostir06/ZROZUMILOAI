"""Admin API for workspace chat logs (Chats Info dashboard)."""
import logging

from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .export_service import (
    build_export_response,
    build_export_timestamp,
    parse_export_format,
    serialize_logs,
)
from .feedback import ALLOWED_FEEDBACK, apply_feedback_fields, save_log_feedback
from .models import WorkspaceChatLog
from .serializers import WorkspaceChatLogSerializer

logger = logging.getLogger(__name__)


class WorkspaceChatLogListView(APIView):
    """Список записаних чатів workspace (лише admin) з фільтрами і пагінацією."""

    permission_classes = (IsAdminUser,)

    def get(self, request):
        try:
            logs = WorkspaceChatLog.objects.select_related('workspace', 'user')

            needs_handoff = request.query_params.get('needs_handoff')
            if needs_handoff in ('1', 'true', 'yes'):
                logs = logs.filter(needs_handoff=True)
            elif needs_handoff in ('0', 'false', 'no'):
                logs = logs.filter(needs_handoff=False)

            feedback = request.query_params.get('feedback')
            if feedback is not None and feedback in ALLOWED_FEEDBACK:
                logs = logs.filter(feedback=feedback)

            try:
                limit = min(max(int(request.query_params.get('limit', 50)), 1), 200)
                offset = max(int(request.query_params.get('offset', 0)), 0)
            except (TypeError, ValueError):
                limit, offset = 50, 0

            total = logs.count()
            page = logs[offset:offset + limit]
            serializer = WorkspaceChatLogSerializer(page, many=True)
            return Response({
                'count': total,
                'limit': limit,
                'offset': offset,
                'results': serializer.data,
            })
        except Exception as exc:
            logger.exception('Помилка отримання списку chat logs: %s', exc)
            return Response(
                {'error': 'Не вдалося завантажити записи чатів'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class WorkspaceChatLogDetailView(APIView):
    """Оновити feedback/handoff або видалити запис Chats Info (admin)."""

    permission_classes = (IsAdminUser,)

    def patch(self, request, log_id):
        try:
            log = WorkspaceChatLog.objects.get(pk=log_id)
        except WorkspaceChatLog.DoesNotExist:
            return Response(
                {'error': 'Запис не знайдено'},
                status=status.HTTP_404_NOT_FOUND,
            )

        error = apply_feedback_fields(log, request.data)
        if error is not None:
            return error

        error = save_log_feedback(log)
        if error is not None:
            return error

        return Response(WorkspaceChatLogSerializer(log).data)

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


class WorkspaceChatLogFeedbackView(APIView):
    """
    Feedback 👍/👎 та handoff для запису чату.

    Власник log або staff. Логи віджета (user_id is None) — лише staff;
    embed feedback йде через Widget-Token API.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request, log_id):
        try:
            log = WorkspaceChatLog.objects.get(pk=log_id)
        except WorkspaceChatLog.DoesNotExist:
            return Response(
                {'error': 'Запис не знайдено'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not request.user.is_staff:
            if log.user_id is None or log.user_id != request.user.pk:
                return Response(
                    {'error': 'Немає доступу до цього запису'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        error = apply_feedback_fields(log, request.data)
        if error is not None:
            return error

        error = save_log_feedback(log)
        if error is not None:
            return error

        return Response(WorkspaceChatLogSerializer(log).data)


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
