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
from .models import WorkspaceChatLog
from .serializers import WorkspaceChatLogSerializer

logger = logging.getLogger(__name__)

# Допустимі значення feedback з UI (👍/👎 або скидання).
_ALLOWED_FEEDBACK = frozenset(('', 'up', 'down'))


def _apply_feedback_fields(log, data):
    """
    Застосувати feedback / needs_handoff з request.data до моделі.

    :return: Response з 400 при невалідних даних, інакше None.
    """
    if 'feedback' in data and data.get('feedback') is not None:
        feedback = str(data.get('feedback')).strip().lower()
        if feedback not in _ALLOWED_FEEDBACK:
            return Response(
                {'error': 'feedback має бути up, down або порожнім'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        log.feedback = feedback

    if 'needs_handoff' in data:
        log.needs_handoff = bool(data.get('needs_handoff'))

    return None


def _save_log_feedback(log):
    """Зберегти feedback-поля; при помилці БД — Response 500."""
    try:
        log.save(update_fields=['feedback', 'needs_handoff'])
    except Exception as exc:
        logger.exception('Не вдалося зберегти feedback для log %s: %s', log.pk, exc)
        return Response(
            {'error': 'Не вдалося зберегти відгук'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return None


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

        error = _apply_feedback_fields(log, request.data)
        if error is not None:
            return error

        error = _save_log_feedback(log)
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

    Доступ: власник log або staff. Якщо log.user_id is None (віджет),
    feedback дозволений будь-якому автентифікованому користувачу —
    для анонімного embed feedback через цей endpoint не передбачений.
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

        if (
            not request.user.is_staff
            and log.user_id
            and log.user_id != request.user.pk
        ):
            return Response(
                {'error': 'Немає доступу до цього запису'},
                status=status.HTTP_403_FORBIDDEN,
            )

        error = _apply_feedback_fields(log, request.data)
        if error is not None:
            return error

        error = _save_log_feedback(log)
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
