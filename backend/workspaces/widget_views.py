"""
Public widget API та admin-управління WidgetToken.

Усі публічні endpoints автентифікуються через Widget-Token.
Відповіді — JSON (DRF Response). Помилки обгортаються у try/except
із зрозумілими HTTP-статусами.
"""
from django.db import DatabaseError
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.throttling import ClientIPScopedRateThrottle
from chats.services import extract_prompt_from_messages
from config.http_utils import validate_chat_messages, validation_error_message
from llm.chat import run_chat

from .models import WidgetToken, Workspace
from .serializers import (
    WidgetTokenCreateSerializer,
    WidgetTokenCreateResponseSerializer,
    WidgetTokenSerializer,
)
from .widget_auth import WidgetTokenAuthentication, WidgetTokenPermission


class WidgetConfigView(APIView):
    """Повернути конфіг workspace для embed-віджета (JSON)."""

    authentication_classes = (WidgetTokenAuthentication,)
    permission_classes = (WidgetTokenPermission,)

    def get(self, request):
        try:
            widget_token = request.auth
            workspace = widget_token.workspace
            model = (workspace.model_names or [None])[0]
            return Response({
                'workspace': {
                    'id': workspace.id,
                    'name': workspace.name,
                    'temperature': workspace.temperature,
                    'model_names': workspace.model_names,
                },
                'model': model,
                'openedx_course_id': (
                    widget_token.openedx_course_id
                    or workspace.meilisearch_course_id
                    or ''
                ),
            })
        except Exception:
            return Response(
                {'error': 'Не вдалося завантажити конфіг віджета'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class WidgetChatView(APIView):
    """
    Чат endpoint, обмежений workspace токена.

    Course scope: якщо openedx_course_id заданий на token або workspace,
    клієнт не може його перевизначити (ACL).
    """

    authentication_classes = (WidgetTokenAuthentication,)
    permission_classes = (WidgetTokenPermission,)
    throttle_classes = (ClientIPScopedRateThrottle,)
    throttle_scope = 'widget_chat'

    def post(self, request):
        widget_token = request.auth
        workspace = widget_token.workspace
        model = (workspace.model_names or [None])[0]
        if model:
            model = str(model).strip()

        if not model:
            return Response(
                {'error': 'Модель не налаштована для workspace'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        messages = request.data.get('messages', [])
        stream = request.data.get('stream', False)

        try:
            validate_chat_messages(messages)
        except ValidationError as exc:
            return Response(
                {'error': validation_error_message(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Оновлення last_used не повинно валити чат при збої БД.
        try:
            widget_token.last_used_at = timezone.now()
            widget_token.save(update_fields=['last_used_at'])
        except DatabaseError:
            pass

        # Token/workspace course scope має пріоритет над клієнтським override.
        locked_course = (
            (widget_token.openedx_course_id or '').strip()
            or (workspace.meilisearch_course_id or '').strip()
        )
        if locked_course:
            course_id = locked_course
        else:
            course_id = (
                (request.data.get('openedx_course_id') or '').strip() or None
            )

        try:
            return run_chat(
                model=model,
                messages=messages,
                stream=stream,
                workspace=workspace,
                user=None,
                prompt=extract_prompt_from_messages(messages),
                meilisearch_course_id=course_id,
            )
        except Exception:
            return Response(
                {'error': 'Помилка обробки чату віджета'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class WidgetTokenListCreateView(APIView):
    """Список / створення widget tokens (лише admin)."""

    permission_classes = (IsAdminUser,)

    def get(self, request, workspace_id):
        workspace = self._get_workspace(workspace_id)
        tokens = workspace.widget_tokens.all()
        serializer = WidgetTokenSerializer(tokens, many=True)
        return Response(serializer.data)

    def post(self, request, workspace_id):
        workspace = self._get_workspace(workspace_id)
        serializer = WidgetTokenCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            raw_token, token = WidgetToken.create_for_workspace(
                workspace,
                label=serializer.validated_data.get('label', ''),
                openedx_course_id=serializer.validated_data.get(
                    'openedx_course_id',
                    '',
                ),
            )
        except Exception:
            return Response(
                {'error': 'Не вдалося створити widget token'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        data = WidgetTokenCreateResponseSerializer(token).data
        data['token'] = raw_token
        return Response(data, status=status.HTTP_201_CREATED)

    def _get_workspace(self, workspace_id):
        try:
            return Workspace.objects.get(pk=workspace_id)
        except Workspace.DoesNotExist as exc:
            raise NotFound('Workspace не знайдено') from exc


class WidgetTokenDeleteView(APIView):
    """Відкликати widget token (лише admin)."""

    permission_classes = (IsAdminUser,)

    def delete(self, request, workspace_id, token_id):
        try:
            token = WidgetToken.objects.get(
                pk=token_id,
                workspace_id=workspace_id,
            )
        except WidgetToken.DoesNotExist:
            return Response(
                {'error': 'Token не знайдено'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            token.delete()
        except DatabaseError:
            return Response(
                {'error': 'Не вдалося видалити token'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response({'deleted': token_id})


class WidgetFeedbackView(APIView):
    """
    Feedback 👍/👎 для запису чату з embed (Widget-Token).

    Доступ лише до логів того ж workspace, що й токен.
    Тіло запиту JSON: {"feedback": "up"|"down"|"", "needs_handoff": bool}.
    """

    authentication_classes = (WidgetTokenAuthentication,)
    permission_classes = (WidgetTokenPermission,)
    throttle_classes = (ClientIPScopedRateThrottle,)
    throttle_scope = 'widget_chat'

    def post(self, request, log_id):
        from chats.log_views import _apply_feedback_fields, _save_log_feedback
        from chats.models import WorkspaceChatLog
        from chats.serializers import WorkspaceChatLogSerializer

        widget_token = request.auth
        try:
            log = WorkspaceChatLog.objects.get(pk=log_id)
        except WorkspaceChatLog.DoesNotExist:
            return Response(
                {'error': 'Запис не знайдено'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DatabaseError:
            return Response(
                {'error': 'Помилка бази даних'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if log.workspace_id != widget_token.workspace_id:
            return Response(
                {'error': 'Немає доступу до цього запису'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            error = _apply_feedback_fields(log, request.data)
            if error is not None:
                return error

            error = _save_log_feedback(log)
            if error is not None:
                return error

            return Response(WorkspaceChatLogSerializer(log).data)
        except Exception:
            return Response(
                {'error': 'Не вдалося зберегти відгук'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
