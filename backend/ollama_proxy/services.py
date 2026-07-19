"""Клієнт HTTP API Ollama."""
import logging

import requests
from django.conf import settings

from config.http_utils import safe_response_json

from .ollama_utils import (
    normalize_model_name,
    normalize_ollama_options,
    raise_for_ollama_status,
    sanitize_messages_for_ollama,
)

logger = logging.getLogger(__name__)


class OllamaService:
    """Обгортка над HTTP API Ollama з переіспользовуванням Session (P1)."""

    def __init__(self, base_url=None, session=None):
        # Базова URL без завершального слеша для коректної конкатенації шляхів.
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip('/')
        self._session = session or requests.Session()

    def _request(self, method, path, **kwargs):
        """Виконати HTTP-запит до Ollama з логуванням помилок мережі."""
        url = f'{self.base_url}{path}'
        timeout = kwargs.pop('timeout', 30)
        try:
            response = self._session.request(method, url, timeout=timeout, **kwargs)
            return response
        except requests.RequestException as exc:
            logger.error('Ollama request failed: %s', exc)
            raise

    def parse_json(self, response):
        """Розпарсити JSON-відповідь Ollama з обробкою некоректного тіла."""
        return safe_response_json(response, service_name='Ollama')

    def list_models(self):
        """Повернути список встановлених моделей."""
        response = self._request('GET', '/api/tags')
        raise_for_ollama_status(response)
        return self.parse_json(response)

    def pull_model(self, name):
        """Pull a model from registry (streaming)."""
        name = normalize_model_name(name)
        response = self._request(
            'POST',
            '/api/pull',
            json={'name': name, 'stream': True},
            stream=True,
            timeout=600,
        )
        raise_for_ollama_status(response)
        return response

    def delete_model(self, name):
        """Delete a model."""
        name = normalize_model_name(name)
        response = self._request(
            'DELETE',
            '/api/delete',
            json={'name': name},
        )
        raise_for_ollama_status(response)
        return self.parse_json(response)

    def chat(self, model, messages, stream=False, options=None):
        """Send chat completion request."""
        model = normalize_model_name(model)
        messages = sanitize_messages_for_ollama(messages)
        options = normalize_ollama_options(options)

        payload = {
            'model': model,
            'messages': messages,
            'stream': stream,
        }
        if options:
            payload['options'] = options
        response = self._request(
            'POST',
            '/api/chat',
            json=payload,
            stream=stream,
            timeout=300,
        )
        raise_for_ollama_status(response)
        return response

    def health(self):
        """Check Ollama availability."""
        try:
            response = self._request('GET', '/api/tags', timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def embed(self, model, text):
        """Отримати embedding-вектор для тексту."""
        model = normalize_model_name(model)
        response = self._request(
            'POST',
            '/api/embeddings',
            json={'model': model, 'prompt': text},
            timeout=120,
        )
        raise_for_ollama_status(response)
        data = self.parse_json(response)
        embedding = data.get('embedding')
        if not isinstance(embedding, list) or not embedding:
            raise requests.RequestException('Ollama не повернув embedding')
        return embedding
