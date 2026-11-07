"""Фабрика LLM-провайдерів. Єдиний провайдер — Ollama."""
import logging

import requests

from .ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)


def resolve_provider(workspace=None, model_name=''):
    """Завжди повернути Ollama. Аргументи лишаються для викликів run_chat."""
    del workspace, model_name
    return OllamaProvider()


def list_all_models():
    """Зібрати моделі Ollama."""
    models = []
    try:
        data = OllamaProvider().list_models()
        for model in data.get('models', []):
            entry = dict(model)
            entry['provider'] = OllamaProvider.provider_id
            models.append(entry)
    except requests.RequestException as exc:
        logger.warning('Не вдалося отримати моделі Ollama: %s', exc)
    return {'models': models}
