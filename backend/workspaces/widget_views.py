"""Public widget API and admin token management."""
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
    """Return workspace config for an embed widget token."""

    authentication_classes = (WidgetTokenAuthentication,)
    permission_classes = (WidgetTokenPermission,)

    def get(self, request):
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


class WidgetChatView(APIView):
    """Chat endpoint scoped to the widget token workspace."""

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

        widget_token.last_used_at = timezone.now()
        widget_token.save(update_fields=['last_used_at'])

        course_id = (
            request.data.get('openedx_course_id')
            or widget_token.openedx_course_id
            or workspace.meilisearch_course_id
            or None
        )

        return run_chat(
            model=model,
            messages=messages,
            stream=stream,
            workspace=workspace,
            user=None,
            prompt=extract_prompt_from_messages(messages),
            meilisearch_course_id=course_id,
        )


class WidgetTokenListCreateView(APIView):
    """List or create widget tokens for a workspace (admin only)."""

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

        raw_token, token = WidgetToken.create_for_workspace(
            workspace,
            label=serializer.validated_data.get('label', ''),
            openedx_course_id=serializer.validated_data.get('openedx_course_id', ''),
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
    """Revoke a widget token (admin only)."""

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
        token.delete()
        return Response({'deleted': token_id})
