"""Telegram Bot API client."""
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

MAX_MESSAGE_CHUNK = 4000


def chunk_text(text: str, max_length: int = MAX_MESSAGE_CHUNK) -> list[str]:
    """Split long text into chunks of at most max_length characters."""
    if not text:
        return [""]
    if len(text) <= max_length:
        return [text]
    return [text[i : i + max_length] for i in range(0, len(text), max_length)]


class TelegramClient:
    """Client for Telegram Bot API operations using requests.Session."""

    def __init__(self, base_url: str = "https://api.telegram.org", session: requests.Session | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def _url(self, token: str, method: str) -> str:
        return f"{self.base_url}/bot{token}/{method}"

    def _parse_response(self, resp: requests.Response, method: str) -> dict[str, Any]:
        """Safely parse response JSON, capturing HTTP errors with status code when non-JSON."""
        try:
            return resp.json()
        except Exception as exc:
            preview = (resp.text or "")[:200]
            logger.warning(
                "Telegram API %s returned non-JSON (status %s): %s (error: %s)",
                method,
                resp.status_code,
                preview,
                exc,
            )
            return {
                "ok": False,
                "description": f"HTTP {resp.status_code}: {preview}" if preview else f"HTTP {resp.status_code}",
            }

    def get_me(self, token: str, timeout: int = 5) -> dict[str, Any]:
        """Validate bot token and fetch bot profile via getMe."""
        url = self._url(token, "getMe")
        try:
            resp = self.session.get(url, timeout=timeout)
            return self._parse_response(resp, "getMe")
        except Exception as exc:
            logger.warning("Failed to call getMe for bot: %s", exc)
            return {"ok": False, "description": str(exc)}

    def get_updates(
        self,
        token: str,
        offset: int | None = None,
        timeout: int = 20,
    ) -> dict[str, Any]:
        """Fetch incoming updates via long polling getUpdates."""
        url = self._url(token, "getUpdates")
        params: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset

        http_timeout = timeout + 10
        try:
            resp = self.session.get(url, params=params, timeout=http_timeout)
            return self._parse_response(resp, "getUpdates")
        except Exception as exc:
            logger.warning("Failed to call getUpdates for bot: %s", exc)
            return {"ok": False, "description": str(exc)}

    def send_message(
        self,
        token: str,
        chat_id: int | str,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str | None = None,
        timeout: int = 10,
    ) -> dict[str, Any]:
        """Send message, chunking if length exceeds 4000 characters."""
        url = self._url(token, "sendMessage")
        chunks = chunk_text(text or "")
        last_result: dict[str, Any] = {"ok": False, "description": "No text sent"}

        for idx, chunk in enumerate(chunks):
            payload: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            # Telegram API requires reply_markup to attach strictly to the final message chunk
            if idx == len(chunks) - 1 and reply_markup is not None:
                payload["reply_markup"] = reply_markup

            try:
                resp = self.session.post(url, json=payload, timeout=timeout)
                last_result = self._parse_response(resp, "sendMessage")
                if not last_result.get("ok"):
                    logger.warning("Telegram sendMessage chunk %s failed: %s", idx, last_result)
                    return last_result
            except Exception as exc:
                logger.warning("Failed to call sendMessage: %s", exc)
                return {"ok": False, "description": str(exc)}

        return last_result

    def send_chat_action(
        self,
        token: str,
        chat_id: int | str,
        action: str = "typing",
        timeout: int = 5,
    ) -> dict[str, Any]:
        """Send chat action (e.g. typing indicator)."""
        url = self._url(token, "sendChatAction")
        payload = {"chat_id": chat_id, "action": action}
        try:
            resp = self.session.post(url, json=payload, timeout=timeout)
            return self._parse_response(resp, "sendChatAction")
        except Exception as exc:
            logger.warning("Failed to call sendChatAction: %s", exc)
            return {"ok": False, "description": str(exc)}

    def answer_callback_query(
        self,
        token: str,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
        timeout: int = 5,
    ) -> dict[str, Any]:
        """Answer incoming callback query from inline buttons."""
        url = self._url(token, "answerCallbackQuery")
        payload: dict[str, Any] = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert,
        }
        if text is not None:
            payload["text"] = text

        try:
            resp = self.session.post(url, json=payload, timeout=timeout)
            return self._parse_response(resp, "answerCallbackQuery")
        except Exception as exc:
            logger.warning("Failed to call answerCallbackQuery: %s", exc)
            return {"ok": False, "description": str(exc)}

    def edit_message_reply_markup(
        self,
        token: str,
        chat_id: int | str,
        message_id: int,
        reply_markup: dict[str, Any] | None = None,
        timeout: int = 5,
    ) -> dict[str, Any]:
        """Edit or remove inline keyboard on an existing message."""
        url = self._url(token, "editMessageReplyMarkup")
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": reply_markup or {},
        }
        try:
            resp = self.session.post(url, json=payload, timeout=timeout)
            return self._parse_response(resp, "editMessageReplyMarkup")
        except Exception as exc:
            logger.warning("Failed to call editMessageReplyMarkup: %s", exc)
            return {"ok": False, "description": str(exc)}
