"""Google Gemini через AI Studio API ключ."""
import json
import logging
import re
import threading

import requests
from django.conf import settings

from .base import BaseLLMProvider, LLMProviderError

logger = logging.getLogger(__name__)

GEMINI_API_BASE = 'https://generativelanguage.googleapis.com/v1beta'
_GEMINI_MODEL_RE = re.compile(r'^[A-Za-z0-9._\-]{1,128}$')


def _sanitize_gemini_model_name(model):
    """Дозволити лише безпечні імена моделей у URL Gemini."""
    name = (model or '').split(':')[0].strip()
    if not _GEMINI_MODEL_RE.fullmatch(name):
        raise LLMProviderError('Недопустиме ім\'я моделі Gemini')
    return name

_session_lock = threading.Lock()
_sessions_by_key = {}


def get_shared_gemini_session(api_key=''):
    """Process-wide Session на api_key (keep-alive)."""
    key = (api_key or '').strip() or '__default__'
    session = _sessions_by_key.get(key)
    if session is not None:
        return session
    with _session_lock:
        session = _sessions_by_key.get(key)
        if session is None:
            session = requests.Session()
            _sessions_by_key[key] = session
        return session


def split_messages_for_gemini(messages):
    """Розділити system prompt і contents для Gemini API."""
    system_parts = []
    contents = []

    for message in messages:
        role = message.get('role')
        content = message.get('content', '')
        if not isinstance(content, str):
            content = str(content)

        if role == 'system':
            if content.strip():
                system_parts.append(content.strip())
        elif role == 'assistant':
            contents.append({'role': 'model', 'parts': [{'text': content}]})
        elif role == 'user':
            contents.append({'role': 'user', 'parts': [{'text': content}]})

    return '\n\n'.join(system_parts), contents


def gemini_text_from_payload(payload):
    """Витягнути текст з відповіді або SSE-чанка Gemini."""
    if not isinstance(payload, dict):
        return ''
    candidates = payload.get('candidates') or []
    if not candidates:
        return ''
    content = candidates[0].get('content') or {}
    parts = content.get('parts') or []
    texts = []
    for part in parts:
        text = part.get('text')
        if isinstance(text, str) and text:
            texts.append(text)
    return ''.join(texts)


def require_gemini_text(payload):
    """Текст з повної відповіді Gemini або LLMProviderError (SAFETY/empty)."""
    if not isinstance(payload, dict):
        raise LLMProviderError('Некоректна відповідь Gemini')
    feedback = payload.get('promptFeedback') or {}
    block_reason = feedback.get('blockReason')
    candidates = payload.get('candidates') or []
    if block_reason and not candidates:
        raise LLMProviderError(f'Відхилено Gemini: {block_reason}')
    text = gemini_text_from_payload(payload)
    if not text.strip():
        raise LLMProviderError('Порожня відповідь Gemini')
    return text


def to_ollama_chunk(text):
    """Нормалізувати фрагмент у формат Ollama SSE для frontend."""
    return json.dumps({
        'message': {'role': 'assistant', 'content': text},
        'done': False,
    })


def to_ollama_response(text):
    """Нормалізувати повну відповідь у формат Ollama."""
    return {
        'message': {'role': 'assistant', 'content': text},
        'done': True,
    }


class GeminiProvider(BaseLLMProvider):
    """Клієнт Gemini Generative Language API."""

    provider_id = 'gemini'

    def __init__(self, api_key=None, session=None):
        self.api_key = (api_key or settings.GEMINI_API_KEY or '').strip()
        # P1: reuse TCP/TLS через Session між запитами одного провайдера.
        self._session = session or get_shared_gemini_session(self.api_key)

    def _require_api_key(self):
        if not self.api_key:
            raise LLMProviderError('GEMINI_API_KEY не налаштовано')

    def _build_payload(self, messages, options=None):
        system_instruction, contents = split_messages_for_gemini(messages)
        if not contents:
            raise LLMProviderError('Повідомлення не можуть бути порожніми')

        payload = {'contents': contents}
        if system_instruction:
            payload['system_instruction'] = {
                'parts': [{'text': system_instruction}],
            }

        generation_config = {}
        if options and options.get('temperature') is not None:
            try:
                generation_config['temperature'] = float(options['temperature'])
            except (TypeError, ValueError) as exc:
                raise LLMProviderError(
                    'Некоректне значення temperature для Gemini',
                ) from exc
        if generation_config:
            payload['generationConfig'] = generation_config

        return payload

    def list_models(self):
        self._require_api_key()
        models = []
        for name in settings.GEMINI_MODEL_NAMES:
            trimmed = name.strip()
            if trimmed:
                models.append({
                    'name': trimmed,
                    'provider': self.provider_id,
                    'size': 0,
                })
        return {'models': models}

    def chat(self, model, messages, stream=False, options=None):
        self._require_api_key()
        model = _sanitize_gemini_model_name(model)
        payload = self._build_payload(messages, options)
        url = f'{GEMINI_API_BASE}/models/{model}:generateContent'

        if stream:
            url = f'{GEMINI_API_BASE}/models/{model}:streamGenerateContent'
            return self._stream_request(url, payload)

        response = self._session.post(
            url,
            params={'key': self.api_key},
            json=payload,
            timeout=300,
        )
        if response.status_code >= 400:
            raise LLMProviderError(self._error_message(response))
        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise LLMProviderError(
                'Некоректна JSON-відповідь від Gemini API',
            ) from exc
        return to_ollama_response(require_gemini_text(data))

    def _stream_request(self, url, payload):
        response = self._session.post(
            url,
            params={'key': self.api_key, 'alt': 'sse'},
            json=payload,
            stream=True,
            timeout=300,
        )
        if response.status_code >= 400:
            try:
                response.read()
            except Exception as exc:
                logger.debug('Failed to read error response body: %s', exc)
            raise LLMProviderError(self._error_message(response))
        return GeminiStreamResponse(response)

    def health(self):
        if not self.api_key:
            return False
        try:
            response = self._session.get(
                f'{GEMINI_API_BASE}/models',
                params={'key': self.api_key},
                timeout=5,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def _error_message(self, response):
        try:
            data = response.json()
            error = data.get('error') or {}
            message = error.get('message')
            if message:
                return message
        except (ValueError, AttributeError) as exc:
            logger.debug('Failed to parse JSON error from Gemini response: %s', exc)
        return f'Gemini API помилка: HTTP {response.status_code}'


class GeminiStreamResponse:
    """Обгортка SSE-відповіді Gemini у iter_lines() для уніфікованого streaming."""

    def __init__(self, response):
        self._response = response

    def close(self):
        """Закрити underlying HTTP response (TCP leak prevention)."""
        try:
            self._response.close()
        except Exception as exc:
            logger.debug('Error closing Gemini stream response: %s', exc)

    def iter_lines(self, decode_unicode=False):
        del decode_unicode
        try:
            for line in self._response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if isinstance(line, bytes):
                    line = line.decode('utf-8')
                if line.startswith('data: '):
                    line = line[6:]
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug('Пропущено некоректний SSE-чанк Gemini')
                    continue
                text = gemini_text_from_payload(payload)
                if text:
                    yield to_ollama_chunk(text).encode('utf-8')
        finally:
            self.close()
