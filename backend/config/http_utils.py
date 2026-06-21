"""Спільні HTTP-утиліти для API та зовнішніх сервісів."""
import json
import logging

import requests
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Допустимі ролі повідомлень у чат-запитах до Ollama.
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


def validate_chat_messages(messages):
    """
    Перевірити структуру списку повідомлень чату.

    :param messages: список dict з ключами role та content
    :raises ValidationError: якщо структура некоректна
    :return: валідований список повідомлень
    """
    if not isinstance(messages, list):
        raise ValidationError({'messages': 'messages має бути списком'})

    for item in messages:
        if not isinstance(item, dict):
            raise ValidationError({'messages': 'Некоректне повідомлення'})
        if item.get('role') not in CHAT_MESSAGE_ROLES:
            raise ValidationError({'messages': 'Некоректна роль повідомлення'})
        if not isinstance(item.get('content'), str):
            raise ValidationError({'messages': 'Некоректний вміст повідомлення'})
        if not item.get('content').strip():
            raise ValidationError({'messages': 'Порожній вміст повідомлення'})

    if not messages:
        raise ValidationError({'messages': 'Список messages не може бути порожнім'})

    return messages
