"""
Спільна логіка чату для різних LLM-провайдерів.

Точка входу для ChatView та WidgetChatView: підготовка повідомлень (RAG),
вибір провайдера, streaming/non-streaming відповідь у форматі Ollama SSE.
"""
import json
import logging

import requests
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.response import Response

from chats.services import (
    content_from_ollama_chunk,
    decode_stream_line,
    extract_response_from_ollama_payload,
    log_workspace_chat_exchange,
)
from workspaces.services import get_ollama_options, prepare_chat_messages
from workspaces.rag.service import extract_last_user_message

from .base import LLMProviderError
from .factory import resolve_provider

logger = logging.getLogger(__name__)


def _provider_error_response(exc, *, stream=False):
    """Уніфікована відповідь API при помилці LLM-провайдера."""
    message = str(exc)
    if stream:
        payload = json.dumps({'error': message})
        return f'data: {payload}\n\n'
    return Response(
        {'error': message},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def run_chat(
    *,
    model,
    messages,
    stream,
    workspace,
    user,
    prompt,
    meilisearch_course_id=None,
):
    """
    Виконати чат-запит і повернути DRF Response або StreamingHttpResponse.

    prompt — текст для логування; якщо None, витягується з messages.

    Streaming: SSE з data: {...} у форматі Ollama; помилки теж у SSE.
    Non-streaming: JSON dict відповіді Ollama або {'error': str}.
    """
    prepared_messages = prepare_chat_messages(
        messages,
        workspace,
        rag_query=extract_last_user_message(messages),
        meilisearch_course_id=meilisearch_course_id,
    )
    options = get_ollama_options(workspace)
    provider = resolve_provider(workspace=workspace, model_name=model)
    log_prompt = prompt if prompt is not None else ''

    if stream:
        def event_stream():
            accumulated = []
            try:
                response = provider.chat(
                    model,
                    prepared_messages,
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
            except (LLMProviderError, requests.RequestException) as exc:
                yield _provider_error_response(exc, stream=True)
            except Exception as exc:
                logger.exception('Unexpected streaming chat error')
                yield _provider_error_response(
                    LLMProviderError('Внутрішня помилка чату'),
                    stream=True,
                )
            else:
                log_workspace_chat_exchange(
                    workspace=workspace,
                    user=user,
                    prompt=log_prompt,
                    response=''.join(accumulated),
                )

        return StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream',
        )

    try:
        parsed = provider.chat(
            model,
            prepared_messages,
            stream=False,
            options=options,
        )
    except (LLMProviderError, requests.RequestException) as exc:
        return _provider_error_response(exc, stream=False)
    except Exception as exc:
        logger.exception('Unexpected chat error')
        return _provider_error_response(
            LLMProviderError('Внутрішня помилка чату'),
            stream=False,
        )

    log_workspace_chat_exchange(
        workspace=workspace,
        user=user,
        prompt=log_prompt,
        response=extract_response_from_ollama_payload(parsed),
    )
    return Response(parsed)
