"""Public widget API and admin token management."""
import json

import requests
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.throttling import ClientIPScopedRateThrottle
from chats.services import (
    content_from_ollama_chunk,
    decode_stream_line,
    extract_prompt_from_messages,
    extract_response_from_ollama_payload,
    log_workspace_chat_exchange,
)
from config.http_utils import validate_chat_messages
from ollama_proxy.services import OllamaService
from workspaces.services import get_ollama_options, prepare_chat_messages
from workspaces.rag.service import extract_last_user_message

from .models import WidgetToken, Workspace
from .serializers import (
    WidgetTokenCreateSerializer,
    WidgetTokenCreateResponseSerializer,
    WidgetTokenSerializer,
)
from .widget_auth import WidgetTokenAuthentication, WidgetTokenPermission


def _validation_message(exc):
    detail = exc.detail
    if isinstance(detail, dict):
        message = next(iter(detail.values()))
        if isinstance(message, list):
            message = message[0]
    else:
        message = str(detail)
    return message


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
            detail = exc.detail
            if isinstance(detail, dict):
                message = next(iter(detail.values()))
                if isinstance(message, list):
                    message = message[0]
            else:
                message = str(detail)
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

        widget_token.last_used_at = timezone.now()
        widget_token.save(update_fields=['last_used_at'])

        ollama_messages = prepare_chat_messages(
            messages,
            workspace,
            rag_query=extract_last_user_message(messages),
        )
        options = get_ollama_options(workspace)
        service = OllamaService()
        prompt = extract_prompt_from_messages(messages)

        if stream:
            def event_stream():
                accumulated = []
                try:
                    response = service.chat(
                        model,
                        ollama_messages,
                        stream=True,
                        options=options,
                    )
                    for line in response.iter_lines():
                        if not line:
                            continue
                        decoded = decode_stream_line(line)
                        if not decoded:
                            continue
                        yield f'data: {decoded}\n\n'
                        chunk_content = content_from_ollama_chunk(decoded)
                        if chunk_content:
                            accumulated.append(chunk_content)
                except ValidationError as exc:
                    payload = json.dumps({'error': _validation_message(exc)})
                    yield f'data: {payload}\n\n'
                except requests.RequestException as exc:
                    payload = json.dumps({'error': str(exc)})
                    yield f'data: {payload}\n\n'
                else:
                    log_workspace_chat_exchange(
                        workspace=workspace,
                        prompt=prompt,
                        response=''.join(accumulated),
                    )

            return StreamingHttpResponse(
                event_stream(),
                content_type='text/event-stream',
            )

        try:
            response = service.chat(
                model,
                ollama_messages,
                stream=False,
                options=options,
            )
            parsed = service.parse_json(response)
            log_workspace_chat_exchange(
                workspace=workspace,
                prompt=prompt,
                response=extract_response_from_ollama_payload(parsed),
            )
            return Response(parsed)
        except ValidationError as exc:
            return Response(
                {'error': _validation_message(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except requests.RequestException as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
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
