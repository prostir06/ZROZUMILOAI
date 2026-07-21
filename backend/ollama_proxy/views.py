"""Views for Ollama proxy API."""
import json

import requests
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.http_utils import (
    validate_chat_messages,
    validation_error_message,
)
from accounts.throttling import ClientIPScopedRateThrottle
from chats.services import extract_prompt_from_messages
from llm.chat import run_chat
from llm.factory import list_all_models
from llm.gemini_provider import GeminiProvider
from llm.ollama_provider import OllamaProvider
from workspaces.services import (
    get_allowed_model_names,
    resolve_workspace_for_chat,
    user_can_use_model,
)

from .services import OllamaService


class OllamaHealthView(APIView):
    """Check LLM provider connection status."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        ollama = OllamaProvider()
        gemini = GeminiProvider()
        ollama_ok = ollama.health()
        return Response({
            'connected': ollama_ok,
            'base_url': ollama.base_url,
            'ollama': {
                'connected': ollama_ok,
                'base_url': ollama.base_url,
            },
            'gemini': {
                'configured': bool(gemini.api_key),
                'connected': gemini.health(),
            },
        })


class ModelListView(APIView):
    """List available models from all configured LLM providers."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        try:
            data = list_all_models()
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

        from django.http import StreamingHttpResponse
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
    """Chat with selected model (Ollama or Gemini)."""

    permission_classes = (IsAuthenticated,)
    throttle_classes = (ClientIPScopedRateThrottle,)
    throttle_scope = 'user_chat'

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
            return Response(
                {'error': validation_error_message(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
            return Response(
                {'error': validation_error_message(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PermissionDenied as exc:
            return Response(
                {'error': str(exc.detail)},
                status=status.HTTP_403_FORBIDDEN,
            )

        return run_chat(
            model=model,
            messages=messages,
            stream=stream,
            workspace=workspace,
            user=request.user,
            prompt=extract_prompt_from_messages(messages),
            meilisearch_course_id=request.data.get('openedx_course_id'),
        )
