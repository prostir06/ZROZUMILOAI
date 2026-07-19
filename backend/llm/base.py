"""Базовий інтерфейс LLM-провайдера."""


class LLMProviderError(Exception):
    """Помилка виклику LLM-провайдера."""


class BaseLLMProvider:
    """Спільний контракт для Ollama, Gemini та інших провайдерів."""

    provider_id = ''

    def list_models(self):
        """Повернути {'models': [{'name': str, ...}]}."""
        raise NotImplementedError

    def chat(self, model, messages, stream=False, options=None):
        """
        Надіслати чат-запит.

        Для stream=True повертає requests.Response з iter_lines().
        Для stream=False повертає dict у форматі Ollama:
        {'message': {'role': 'assistant', 'content': str}}.
        """
        raise NotImplementedError

    def health(self):
        """Чи доступний провайдер."""
        raise NotImplementedError
