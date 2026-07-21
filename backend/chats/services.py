"""Сервіс логування чатів workspace для адмін-пашборду Chats Info."""
import json
import logging

from django.db import DatabaseError

from workspaces.rag.service import extract_last_user_message

from .models import WorkspaceChatLog

logger = logging.getLogger(__name__)

# Мітка для анонімних користувачів (widget без авторизації).
UNKNOWN_USER_LABEL = 'unknown user'


def sent_by_label_for_user(user):
    """
    Сформувати відображуване ім'я автора повідомлення.

    Пріоритет: повне ім'я → username → «unknown user».
    """
    if user and getattr(user, 'is_authenticated', False):
        try:
            full_name = user.get_full_name().strip()
        except AttributeError:
            full_name = ''
        if full_name:
            return full_name
        return getattr(user, 'username', UNKNOWN_USER_LABEL) or UNKNOWN_USER_LABEL
    return UNKNOWN_USER_LABEL


def extract_prompt_from_messages(messages):
    """
    Отримати текст останнього user-повідомлення для запису в лог.

    Повертає порожній рядок, якщо повідомлень немає або структура некоректна.
    """
    try:
        return extract_last_user_message(messages) or ''
    except (TypeError, AttributeError) as exc:
        logger.warning('Не вдалося витягнути prompt з messages: %s', exc)
        return ''


def extract_response_from_ollama_payload(payload):
    """
    Витягнути текст відповіді асистента з JSON Ollama.

    Підтримує формати chat (`message.content`) та generate (`response`).
    """
    if not isinstance(payload, dict):
        return ''
    message = payload.get('message')
    if isinstance(message, dict):
        content = message.get('content')
        return content if isinstance(content, str) else ''
    response = payload.get('response')
    return response if isinstance(response, str) else ''


def content_from_ollama_chunk(raw_chunk):
    """
    Витягнути фрагмент відповіді з одного SSE-чанка Ollama.

    Пошкоджений JSON ігнорується — streaming не переривається.
    """
    if not raw_chunk:
        return ''
    try:
        payload = json.loads(raw_chunk)
    except (TypeError, json.JSONDecodeError) as exc:
        logger.debug('Пропущено некоректний SSE-чанк Ollama: %s', exc)
        return ''
    return extract_response_from_ollama_payload(payload)


def decode_stream_line(line):
    """
    Декодувати байтовий рядок SSE у UTF-8.

    :return: рядок або None, якщо декодування не вдалося
    """
    if not line:
        return None
    try:
        return line.decode('utf-8')
    except UnicodeDecodeError as exc:
        logger.warning('Пропущено SSE-рядок з некоректним UTF-8: %s', exc)
        return None


def log_workspace_chat_exchange(
    *,
    workspace,
    user=None,
    sent_by='',
    prompt='',
    response='',
    needs_handoff=False,
):
    """
    Зберегти обмін prompt/response у БД для Chats Info.

    Помилки БД логуються, але не переривають основний чат-запит.
    """
    prompt = (prompt or '').strip()
    if not workspace or not prompt:
        return None

    label = (sent_by or '').strip() or sent_by_label_for_user(user)
    authenticated_user = (
        user if user and getattr(user, 'is_authenticated', False) else None
    )

    try:
        return WorkspaceChatLog.objects.create(
            user=authenticated_user,
            sent_by=label,
            workspace=workspace,
            prompt=prompt,
            response=response or '',
            needs_handoff=bool(needs_handoff),
        )
    except DatabaseError as exc:
        logger.exception(
            'Не вдалося зберегти workspace chat log (workspace=%s): %s',
            getattr(workspace, 'pk', workspace),
            exc,
        )
        return None
