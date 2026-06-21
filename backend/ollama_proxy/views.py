"""Views for Ollama proxy API."""
import json

import requests
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.http_utils import validate_chat_messages
from chats.services import (
    content_from_ollama_chunk,
    decode_stream_line,
    extract_prompt_from_messages,
    extract_response_from_ollama_payload,
    log_workspace_chat_exchange,
)
from workspaces.services import (
    get_allowed_model_names,
    get_ollama_options,
    prepare_chat_messages,
    resolve_workspace_for_chat,
    user_can_use_model,
)
from workspaces.rag.service import extract_last_user_message

from .services import OllamaService


def _validation_message(exc):
    """Перетворити ValidationError у рядок для API."""
    detail = exc.detail
    if isinstance(detail, dict):
        message = next(iter(detail.values()))
        if isinstance(message, list):
            message = message[0]
    else:
        message = str(detail)
    return message


class OllamaHealthView(APIView):
    """Check Ollama connection status."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        service = OllamaService()
        is_healthy = service.health()
        return Response({
            'connected': is_healthy,
            'base_url': service.base_url,
        })


class ModelListView(APIView):
    """List installed Ollama models."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        service = OllamaService()
        try:
            data = service.list_models()
            allowed = get_allowed_model_names(request.user)
            if allowed is not None:
                models = data.get('models', [])
                data['models'] = [
                    model for model in models
                    if model.get('name') in allowed
                ]
            return Response(data)
        except requests.RequestException as exc:
            return Response(
                {'error': f'Не вдалося підключитися до Ollama: {exc}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class ModelPullView(APIView):
    """Pull (download) a new model with streaming progress."""

    permission_classes = (IsAdminUser,)

    def post(self, request):
        name = request.data.get('name')
        if not name:
            return Response(
                {'error': 'Параметр name обов\'язковий'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = OllamaService()

        def event_stream():
            try:
                response = service.pull_model(name)
                for line in response.iter_lines():
                    if line:
                        yield f'data: {line.decode("utf-8")}\n\n'
                yield 'data: {"status":"done"}\n\n'
            except requests.RequestException as exc:
                payload = json.dumps({'error': str(exc)})
                yield f'data: {payload}\n\n'

        return StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream',
        )


class ModelDeleteView(APIView):
    """Delete an installed model."""

    permission_classes = (IsAdminUser,)

    def delete(self, request):
        name = request.data.get('name')
        if not name:
            return Response(
                {'error': 'Параметр name обов\'язковий'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = OllamaService()
        try:
            data = service.delete_model(name)
            return Response(data)
        except requests.RequestException as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class ChatView(APIView):
    """Chat with selected Ollama model."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        model = (request.data.get('model') or '').strip()
        messages = request.data.get('messages', [])
        stream = request.data.get('stream', False)
        workspace_id = request.data.get('workspace_id')

        if not model:
            return Response(
                {'error': 'Параметр model обов\'язковий'},
                status=status.HTTP_400_BAD_REQUEST,
            )

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

        if not user_can_use_model(request.user, model):
            return Response(
                {'error': 'Модель недоступна для вашого workspace'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            workspace = resolve_workspace_for_chat(
                request.user,
                model,
                workspace_id,
            )
        except ValidationError as exc:
            detail = exc.detail
            if isinstance(detail, dict):
                message = next(iter(detail.values()))
                if isinstance(message, list):
                    message = message[0]
            else:
                message = str(detail)
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as exc:
            return Response(
                {'error': str(exc.detail)},
                status=status.HTTP_403_FORBIDDEN,
            )

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
                        user=request.user,
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
                user=request.user,
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
