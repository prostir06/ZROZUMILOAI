"""Утиліти для запитів до Ollama API."""
import json
import logging

import requests
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)


def parse_ollama_error(response):
    """Витягнути текст помилки з HTTP-відповіді Ollama."""
    try:
        body = response.json()
        if isinstance(body, dict):
            return body.get('error') or body.get('message') or response.text[:500]
    except (ValueError, json.JSONDecodeError) as exc:
        logger.debug('Ollama error response is not JSON: %s', exc)
    text = (response.text or '').strip()
    return text[:500] if text else f'HTTP {response.status_code}'


def raise_for_ollama_status(response):
    """
    Перевірити status_code і кинути RequestException з текстом помилки Ollama.

    Замість «400 Client Error: Bad Request for url: ...» користувач бачить
    змістовне повідомлення, наприклад «model is required».
    """
    if response.ok:
        return

    detail = parse_ollama_error(response)
    logger.error('Ollama HTTP %s: %s', response.status_code, detail)
    raise requests.RequestException(f'Ollama: {detail}')


def normalize_model_name(model):
    """
    Нормалізувати ім'я моделі перед запитом до Ollama.

    :raises ValidationError: якщо ім'я порожнє після trim
    """
    normalized = str(model or '').strip()
    if not normalized:
        raise ValidationError({'model': 'Параметр model обов\'язковий'})
    return normalized


def sanitize_messages_for_ollama(messages):
    """
    Підготувати messages для /api/chat: лише role/content, без порожніх рядків.

    :raises ValidationError: якщо немає жодного user-повідомлення
    """
    cleaned = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        content = item.get('content')
        if role not in ('user', 'assistant', 'system'):
            continue
        if not isinstance(content, str):
            continue
        content = content.strip()
        if not content:
            continue
        cleaned.append({'role': role, 'content': content})

    if not any(msg['role'] == 'user' for msg in cleaned):
        raise ValidationError({'messages': 'Потрібне хоча б одне user-повідомлення'})

    return cleaned


def normalize_ollama_options(options):
    """Перетворити options на безпечні типи для Ollama."""
    if not options:
        return None

    normalized = {}
    temperature = options.get('temperature')
    if temperature is not None:
        try:
            normalized['temperature'] = float(temperature)
        except (TypeError, ValueError) as exc:
            raise ValidationError({'temperature': 'Некоректне значення temperature'}) from exc

    num_predict = options.get('num_predict')
    if num_predict is not None:
        try:
            limit = int(num_predict)
        except (TypeError, ValueError) as exc:
            raise ValidationError({'num_predict': 'Некоректне значення num_predict'}) from exc
        if limit < 1 or limit > 2048:
            raise ValidationError({'num_predict': 'num_predict має бути від 1 до 2048'})
        normalized['num_predict'] = limit

    num_ctx = options.get('num_ctx')
    if num_ctx is not None:
        try:
            context = int(num_ctx)
        except (TypeError, ValueError) as exc:
            raise ValidationError({'num_ctx': 'Некоректне значення num_ctx'}) from exc
        if context < 256 or context > 8192:
            raise ValidationError({'num_ctx': 'num_ctx має бути від 256 до 8192'})
        normalized['num_ctx'] = context

    return normalized or None
