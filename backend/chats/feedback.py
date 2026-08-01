"""
Спільна логіка feedback / handoff для panel і widget API.

Винесено з log_views, щоб уникнути імпорту private-хелперів у widget_views.
Усі помилки валідації/збереження повертаються як DRF Response, а не raise.
"""
import logging

from django.db import DatabaseError
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger(__name__)

# Допустимі значення з UI (👍/👎) або скидання порожнім рядком.
ALLOWED_FEEDBACK = frozenset(('', 'up', 'down'))


def apply_feedback_fields(log, data):
    """
    Застосувати feedback / needs_handoff з request.data до моделі (без save).

    :param log: екземпляр WorkspaceChatLog
    :param data: dict-подібне тіло запиту
    :return: Response з 400 при невалідних даних, інакше None
    """
    if data is None:
        return Response(
            {'error': 'Порожнє тіло запиту'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        if 'feedback' in data and data.get('feedback') is not None:
            feedback = str(data.get('feedback')).strip().lower()
            if feedback not in ALLOWED_FEEDBACK:
                return Response(
                    {'error': 'feedback має бути up, down або порожнім'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            log.feedback = feedback

        if 'needs_handoff' in data:
            # bool('false') == True у Python — приймаємо явні булеві / 0/1 / рядки.
            raw = data.get('needs_handoff')
            if isinstance(raw, bool):
                log.needs_handoff = raw
            elif isinstance(raw, (int, float)):
                log.needs_handoff = bool(raw)
            elif isinstance(raw, str):
                normalized = raw.strip().lower()
                if normalized in ('1', 'true', 'yes', 'on'):
                    log.needs_handoff = True
                elif normalized in ('0', 'false', 'no', 'off', ''):
                    log.needs_handoff = False
                else:
                    return Response(
                        {'error': 'needs_handoff має бути true/false'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                log.needs_handoff = bool(raw)
    except (TypeError, AttributeError, ValueError) as exc:
        logger.warning('Invalid feedback payload: %s', exc)
        return Response(
            {'error': 'Некоректні дані feedback'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return None


def save_log_feedback(log):
    """
    Зберегти feedback-поля в БД.

    :return: Response 500 при помилці БД, інакше None
    """
    try:
        log.save(update_fields=['feedback', 'needs_handoff'])
    except DatabaseError as exc:
        logger.exception(
            'Не вдалося зберегти feedback для log %s: %s',
            getattr(log, 'pk', None),
            exc,
        )
        return Response(
            {'error': 'Не вдалося зберегти відгук'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            'Unexpected feedback save error for log %s: %s',
            getattr(log, 'pk', None),
            exc,
        )
        return Response(
            {'error': 'Не вдалося зберегти відгук'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return None
