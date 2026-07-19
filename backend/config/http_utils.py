"""Спільні HTTP-утиліти для API та зовнішніх сервісів."""
import json
import logging

import requests
from django.conf import settings
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Допустимі ролі повідомлень у чат-запитах.
CHAT_MESSAGE_ROLES = frozenset({'user', 'assistant', 'system'})


def safe_response_json(response, service_name='сервісу'):
    """
    Безпечно розпарсити JSON із HTTP-відповіді.

    :param response: об'єкт requests.Response
    :param service_name: назва джерела для повідомлення про помилку
    :raises requests.RequestException: якщо тіло відповіді не є валідним JSON
    """
    try:
        return response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error('Invalid JSON from %s: %s', service_name, exc)
        raise requests.RequestException(
            f'Некоректна відповідь від {service_name}',
        ) from exc


def validation_error_message(exc):
    """
    Перетворити DRF ValidationError.detail у рядок для API-відповіді.

    Єдина реалізація для ollama_proxy та widget_views (P1 дедуп).
    """
    detail = getattr(exc, 'detail', exc)
    if isinstance(detail, dict):
        message = next(iter(detail.values()))
        if isinstance(message, list):
            return str(message[0])
        return str(message)
    if isinstance(detail, list) and detail:
        return str(detail[0])
    return str(detail)


def validate_chat_messages(messages):
    """
    Перевірити структуру та розмір списку повідомлень чату.

    Ліміти керуються settings.CHAT_MAX_MESSAGES / CHAT_MAX_MESSAGE_CHARS /
    CHAT_MAX_TOTAL_CHARS (P0 DoS-захист).

    :param messages: список dict з ключами role та content
    :raises ValidationError: якщо структура некоректна
    :return: валідований список повідомлень
    """
    if not isinstance(messages, list):
        raise ValidationError({'messages': 'messages має бути списком'})

    if not messages:
        raise ValidationError({'messages': 'Список messages не може бути порожнім'})

    max_messages = getattr(settings, 'CHAT_MAX_MESSAGES', 100)
    max_chars = getattr(settings, 'CHAT_MAX_MESSAGE_CHARS', 16000)
    max_total = getattr(settings, 'CHAT_MAX_TOTAL_CHARS', 120000)

    if len(messages) > max_messages:
        raise ValidationError({
            'messages': f'Забагато повідомлень (макс. {max_messages})',
        })

    total_chars = 0
    for item in messages:
        if not isinstance(item, dict):
            raise ValidationError({'messages': 'Некоректне повідомлення'})
        if item.get('role') not in CHAT_MESSAGE_ROLES:
            raise ValidationError({'messages': 'Некоректна роль повідомлення'})
        content = item.get('content')
        if not isinstance(content, str):
            raise ValidationError({'messages': 'Некоректний вміст повідомлення'})
        if not content.strip():
            raise ValidationError({'messages': 'Порожній вміст повідомлення'})
        if len(content) > max_chars:
            raise ValidationError({
                'messages': f'Повідомлення задовге (макс. {max_chars} символів)',
            })
        total_chars += len(content)

    if total_chars > max_total:
        raise ValidationError({
            'messages': f'Сумарний розмір messages перевищує {max_total} символів',
        })

    return messages
