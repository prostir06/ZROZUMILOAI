"""Адаптер Ollama до спільного інтерфейсу LLM."""
import requests
from rest_framework.exceptions import ValidationError

from config.http_utils import validation_error_message
from ollama_proxy.services import OllamaService

from .base import BaseLLMProvider, LLMProviderError


class OllamaProvider(BaseLLMProvider):
    """
    Обгортка над OllamaService.

    Усі помилки мапляться в LLMProviderError, щоб run_chat мав єдиний контракт
    відповіді незалежно від провайдера (Ollama чи Gemini).
    """

    provider_id = 'ollama'

    def __init__(self, base_url=None):
        self._service = OllamaService(base_url=base_url)

    @property
    def base_url(self):
        return self._service.base_url

    def list_models(self):
        """Список моделей Ollama; мережеві помилки повертаються як RequestException."""
        return self._service.list_models()

    def chat(self, model, messages, stream=False, options=None):
        """
        Чат через Ollama API.

        ValidationError та RequestException → LLMProviderError.
        """
        try:
            response = self._service.chat(
                model,
                messages,
                stream=stream,
                options=options,
            )
        except ValidationError as exc:
            raise LLMProviderError(validation_error_message(exc)) from exc
        except requests.RequestException as exc:
            raise LLMProviderError(str(exc)) from exc

        if stream:
            return response

        try:
            return self._service.parse_json(response)
        except requests.RequestException as exc:
            raise LLMProviderError(str(exc)) from exc

    def health(self):
        return self._service.health()
