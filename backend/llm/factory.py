"""Фабрика та агрегація LLM-провайдерів."""
import logging

import requests
from django.conf import settings

from workspaces.models import Workspace
from workspaces.services import get_gemini_api_key

from .base import LLMProviderError
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)


def is_gemini_model(model_name):
    """Чи належить ім'я моделі до списку Gemini."""
    base = (model_name or '').split(':')[0].strip()
    return base in settings.GEMINI_MODEL_NAMES


def get_provider(provider_id, workspace=None):
    """Отримати провайдера за ідентифікатором."""
    if provider_id == Workspace.LLMProvider.GEMINI:
        return GeminiProvider(api_key=get_gemini_api_key(workspace))
    return OllamaProvider()


def resolve_provider(workspace=None, model_name=''):
    """
    Визначити провайдера за workspace або ім'ям моделі.

    Пріоритет:
    1. workspace.llm_provider — явний вибір у налаштуваннях workspace
    2. ім'я моделі з GEMINI_MODEL_NAMES — якщо workspace не передано
    3. Ollama — за замовчуванням
    """
    if workspace is not None:
        return get_provider(workspace.llm_provider, workspace=workspace)

    if is_gemini_model(model_name):
        return GeminiProvider(api_key=get_gemini_api_key())

    return OllamaProvider()


def list_gemini_models():
    """Статичний список моделей Gemini з налаштувань."""
    return [
        {
            'name': name,
            'provider': GeminiProvider.provider_id,
            'size': 0,
        }
        for name in settings.GEMINI_MODEL_NAMES
    ]


def list_all_models():
    """Зібрати моделі з усіх доступних провайдерів."""
    models = []

    try:
        ollama = OllamaProvider()
        data = ollama.list_models()
        for model in data.get('models', []):
            entry = dict(model)
            entry['provider'] = OllamaProvider.provider_id
            models.append(entry)
    except requests.RequestException as exc:
        logger.warning('Не вдалося отримати моделі Ollama: %s', exc)

    models.extend(list_gemini_models())

    return {'models': models}
