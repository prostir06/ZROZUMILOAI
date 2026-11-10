"""
Спільна логіка чату для різних LLM-провайдерів.

Точка входу для ChatView та WidgetChatView: підготовка повідомлень (RAG),
вибір провайдера, streaming/non-streaming відповідь у форматі Ollama SSE.
Sources (citations) відправляються окремим SSE-події `sources` або полем JSON.
"""
import json
import logging

import requests
from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.response import Response

from chats.services import (
    content_from_ollama_chunk,
    decode_stream_line,
    extract_response_from_ollama_payload,
    log_workspace_chat_exchange,
)
from workspaces.rag.service import extract_last_user_message
from workspaces.services import (
    get_ollama_options,
    prepare_chat_messages,
)

from .admission import (
    OLLAMA_BUSY_CODE,
    OLLAMA_BUSY_MESSAGE,
    RETRY_AFTER_SECONDS,
    OllamaBusy,
    acquire_ollama_slot,
    release_ollama_slot,
)
from .base import LLMProviderError
from .factory import resolve_provider

logger = logging.getLogger(__name__)


def _ollama_busy_response():
    response = Response(
        {'error': OLLAMA_BUSY_MESSAGE, 'code': OLLAMA_BUSY_CODE},
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )
    response['Retry-After'] = RETRY_AFTER_SECONDS
    return response


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


def _safe_score(value):
    """Перетворити score у float; некоректні значення → 0.0."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _needs_handoff_from_sources(sources):
    """
    True, якщо найкращий RAG score нижчий за поріг (ескалація до людини).

    Порожні sources не ескалюємо — це може бути чат без RAG або збій пошуку.
    """
    if not sources:
        return False
    try:
        min_score = float(getattr(settings, 'RAG_MIN_SCORE', 0.25))
    except (TypeError, ValueError):
        min_score = 0.25
    best = max(_safe_score(item.get('score')) for item in sources)
    return best < min_score


def _prepare_chat_context(messages, workspace, meilisearch_course_id):
    """
    Підготувати messages + sources для провайдера.

    Помилки RAG/Meili не повинні валити весь чат — працюємо без контексту.
    """
    try:
        return prepare_chat_messages(
            messages,
            workspace,
            rag_query=extract_last_user_message(messages),
            meilisearch_course_id=meilisearch_course_id,
        )
    except Exception:
        logger.exception('RAG/chat prep failed; continuing without context')
        return list(messages), []


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

    Streaming: спочатку data: {"sources":[...]}, далі Ollama SSE-чанки,
    наприкінці data: {"log_id":..., "needs_handoff":...}.
    Non-streaming: JSON з message + sources + log_id.
    """
    prepared_messages, sources = _prepare_chat_context(
        messages,
        workspace,
        meilisearch_course_id,
    )
    needs_handoff = _needs_handoff_from_sources(sources)
    options = get_ollama_options(workspace)
    try:
        provider = resolve_provider(workspace=workspace, model_name=model)
    except Exception as exc:
        logger.exception('Failed to resolve LLM provider')
        return _provider_error_response(
            LLMProviderError(str(exc) or 'Провайдер недоступний'),
            stream=stream,
        )
    log_prompt = prompt if prompt is not None else ''

    try:
        slot_token = acquire_ollama_slot()
    except OllamaBusy:
        logger.warning(
            'Ollama busy (workspace=%s)',
            getattr(workspace, 'pk', None),
        )
        return _ollama_busy_response()

    if stream:
        def event_stream():
            accumulated = []
            response = None

            try:
                if sources:
                    yield f'data: {json.dumps({"sources": sources})}\n\n'

                try:
                    response = provider.chat(
                        model,
                        prepared_messages,
                        stream=True,
                        options=options,
                    )
                except (LLMProviderError, requests.RequestException) as exc:
                    logger.warning(
                        'Streaming LLM error (workspace=%s, model=%s): %s',
                        getattr(workspace, 'pk', None),
                        model,
                        exc,
                        exc_info=True,
                    )
                    yield _provider_error_response(exc, stream=True)
                    return
                except Exception:
                    logger.exception('Unexpected streaming chat error')
                    yield _provider_error_response(
                        LLMProviderError('Внутрішня помилка чату'),
                        stream=True,
                    )
                    return

                try:
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
                    logger.warning(
                        'Streaming LLM error (workspace=%s, model=%s): %s',
                        getattr(workspace, 'pk', None),
                        model,
                        exc,
                        exc_info=True,
                    )
                    yield _provider_error_response(exc, stream=True)
                except Exception:
                    logger.exception('Unexpected streaming chat error')
                    yield _provider_error_response(
                        LLMProviderError('Внутрішня помилка чату'),
                        stream=True,
                    )
                else:
                    log = log_workspace_chat_exchange(
                        workspace=workspace,
                        user=user,
                        prompt=log_prompt,
                        response=''.join(accumulated),
                        needs_handoff=needs_handoff,
                    )
                    meta = {'needs_handoff': needs_handoff}
                    if log:
                        meta['log_id'] = log.pk
                        yield f'data: {json.dumps(meta)}\n\n'
            finally:
                release_ollama_slot(slot_token)
                if response is not None and hasattr(response, 'close'):
                    try:
                        response.close()
                    except Exception as exc:
                        logger.warning(
                            'Error closing stream response: %s',
                            exc,
                            exc_info=True,
                        )

        return StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream',
        )

    try:
        try:
            parsed = provider.chat(
                model,
                prepared_messages,
                stream=False,
                options=options,
            )
        except (LLMProviderError, requests.RequestException) as exc:
            logger.warning(
                'Chat provider error (workspace=%s, model=%s): %s',
                getattr(workspace, 'pk', None),
                model,
                exc,
                exc_info=True,
            )
            return _provider_error_response(exc, stream=False)
        except Exception:
            logger.exception('Unexpected chat error')
            return _provider_error_response(
                LLMProviderError('Внутрішня помилка чату'),
                stream=False,
            )

        if isinstance(parsed, dict):
            parsed = dict(parsed)
            parsed['sources'] = sources
            parsed['needs_handoff'] = needs_handoff

        log = log_workspace_chat_exchange(
            workspace=workspace,
            user=user,
            prompt=log_prompt,
            response=extract_response_from_ollama_payload(parsed),
            needs_handoff=needs_handoff,
        )
        if isinstance(parsed, dict) and log:
            parsed['log_id'] = log.pk
        return Response(parsed)
    finally:
        release_ollama_slot(slot_token)
