"""Ollama API client service."""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class OllamaService:
    """Wrapper for Ollama HTTP API."""

    def __init__(self, base_url=None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip('/')

    def _request(self, method, path, **kwargs):
        url = f'{self.base_url}{path}'
        timeout = kwargs.pop('timeout', 30)
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
            return response
        except requests.RequestException as exc:
            logger.error('Ollama request failed: %s', exc)
            raise

    def list_models(self):
        """Return installed models."""
        response = self._request('GET', '/api/tags')
        response.raise_for_status()
        return response.json()

    def pull_model(self, name):
        """Pull a model from registry (streaming)."""
        response = self._request(
            'POST',
            '/api/pull',
            json={'name': name, 'stream': True},
            stream=True,
            timeout=600,
        )
        response.raise_for_status()
        return response

    def delete_model(self, name):
        """Delete a model."""
        response = self._request(
            'DELETE',
            '/api/delete',
            json={'name': name},
        )
        response.raise_for_status()
        return response.json()

    def chat(self, model, messages, stream=False, options=None):
        """Send chat completion request."""
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
        response.raise_for_status()
        return response

    def generate(self, model, prompt, stream=False):
        """Send generate request."""
        payload = {
            'model': model,
            'prompt': prompt,
            'stream': stream,
        }
        response = self._request(
            'POST',
            '/api/generate',
            json=payload,
            stream=stream,
            timeout=300,
        )
        response.raise_for_status()
        return response

    def health(self):
        """Check Ollama availability."""
        try:
            response = self._request('GET', '/api/tags', timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False
