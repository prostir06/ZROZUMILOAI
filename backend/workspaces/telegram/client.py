"""Telegram Bot API client."""
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class TelegramClient:
    """Client for Telegram Bot API operations."""

    def __init__(self, base_url: str = 'https://api.telegram.org'):
        self.base_url = base_url.rstrip('/')

    def get_me(self, token: str) -> dict[str, Any]:
        """Validate bot token and fetch bot profile via getMe."""
        url = f'{self.base_url}/bot{token}/getMe'
        try:
            resp = requests.get(url, timeout=10)
            return resp.json()
        except Exception as exc:
            logger.warning('Failed to call getMe for bot: %s', exc)
            return {'ok': False, 'description': str(exc)}
