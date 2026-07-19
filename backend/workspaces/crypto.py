"""
Шифрування чутливих полів workspace (API keys) at rest.

Використовує Fernet з ключем, похідним від FIELD_ENCRYPTION_KEY або
DJANGO_SECRET_KEY. Значення зберігаються з префіксом enc:v1: для
зворотної сумісності з уже збереженими plaintext-ключами.
"""
import base64
import hashlib
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Префікс ciphertext у БД — щоб відрізнити від legacy plaintext.
_ENC_PREFIX = 'enc:v1:'


def _fernet():
    """Побудувати Fernet з налаштувань (lazy, без глобального стану модуля)."""
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError(
            'Пакет cryptography обовʼязковий для шифрування ключів workspace',
        ) from exc

    raw = (
        getattr(settings, 'FIELD_ENCRYPTION_KEY', '')
        or settings.SECRET_KEY
        or ''
    ).encode('utf-8')
    # Fernet потребує url-safe base64 32-byte ключ.
    digest = hashlib.sha256(raw).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value):
    """
    Зашифрувати рядок для збереження у БД.

    Порожній рядок лишається порожнім (ключ «очищено»).
    """
    if value is None:
        return ''
    text = str(value).strip()
    if not text:
        return ''
    if text.startswith(_ENC_PREFIX):
        return text
    try:
        token = _fernet().encrypt(text.encode('utf-8')).decode('ascii')
        return f'{_ENC_PREFIX}{token}'
    except Exception as exc:
        logger.error('encrypt_secret failed: %s', exc)
        raise


def decrypt_secret(value):
    """
    Розшифрувати значення з БД.

    Legacy plaintext (без префікса) повертається як є.
    """
    if value is None:
        return ''
    text = str(value)
    if not text:
        return ''
    if not text.startswith(_ENC_PREFIX):
        return text
    token = text[len(_ENC_PREFIX):]
    try:
        return _fernet().decrypt(token.encode('ascii')).decode('utf-8')
    except Exception as exc:
        logger.error('decrypt_secret failed: %s', exc)
        return ''
