"""Telegram Long Polling daemon and worker threads."""
import logging
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from workspaces.models import TelegramBot
from workspaces.telegram.client import TelegramClient
from workspaces.telegram.handlers import handle_telegram_update

logger = logging.getLogger(__name__)

HEARTBEAT_PATH = Path(
    os.getenv(
        "TELEGRAM_POLLER_HEARTBEAT_PATH",
        str(Path(tempfile.gettempdir()) / "poller.heartbeat"),
    ),
)

# Atomic Lua script: extends TTL if key is held by this worker UUID, else acquires with SET NX EX
_RENEW_OR_ACQUIRE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    redis.call('expire', KEYS[1], ARGV[2])
    return 1
else
    return redis.call('set', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[2])
end
"""

# Atomic release: ensures worker only deletes its own lock, avoiding freeing a successor's lock
_RELEASE_LOCK_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


def _get_redis_client():
    if not (getattr(settings, "REDIS_URL", "") or "").strip():
        return None
    try:
        from django_redis import get_redis_connection

        return get_redis_connection("default")
    except Exception as exc:
        logger.warning("Redis connection unavailable for telegram poll lock: %s", exc)
        return None


class TelegramBotWorker(threading.Thread):
    """Worker thread performing continuous long polling for a single Telegram bot."""

    def __init__(
        self,
        bot_id: int,
        stop_event: threading.Event | None = None,
        client: TelegramClient | None = None,
    ):
        super().__init__(name=f"TelegramBotWorker-{bot_id}", daemon=True)
        self.bot_id = bot_id
        self.stop_event = stop_event or threading.Event()
        self.client = client or TelegramClient()
        self.lock_token = uuid.uuid4().hex
        self._error_streak = 0

    def _acquire_or_renew_lock(self) -> bool:
        redis_url = (getattr(settings, "REDIS_URL", "") or "").strip()
        if not redis_url:
            # Local dev without Redis: proceed without distributed lock
            return True

        redis_client = _get_redis_client()
        if redis_client is None:
            logger.error(
                "Redis client unavailable for bot %s while REDIS_URL is set (failing closed)",
                self.bot_id,
            )
            return False

        key = f"telegram:poll_lock:{self.bot_id}"
        try:
            res = redis_client.eval(_RENEW_OR_ACQUIRE_LUA, 1, key, self.lock_token, 60)
            return bool(res)
        except Exception as exc:
            logger.error(
                "Redis error acquiring poll lock for bot %s while REDIS_URL is set (failing closed): %s",
                self.bot_id,
                exc,
                exc_info=True,
            )
            return False

    def _release_lock(self) -> None:
        redis_client = _get_redis_client()
        if redis_client is None:
            return

        key = f"telegram:poll_lock:{self.bot_id}"
        try:
            redis_client.eval(_RELEASE_LOCK_LUA, 1, key, self.lock_token)
        except Exception as exc:
            logger.warning("Error releasing telegram poll lock: %s", exc)

    def step(self) -> bool:
        """
        Execute a single poll iteration.

        Returns False if the worker should stop (bot missing or inactive).
        """
        try:
            bot = TelegramBot.objects.select_related("workspace").get(pk=self.bot_id)
        except TelegramBot.DoesNotExist:
            logger.info("Bot %s does not exist, worker exiting.", self.bot_id)
            return False

        if not bot.is_active or not bot.workspace:
            logger.info("Bot %s is inactive or unassigned, worker exiting.", self.bot_id)
            return False

        token = bot.get_token()
        if not token:
            bot.last_error = "Відсутній токен"
            bot.save(update_fields=["last_error", "updated_at"])
            self.stop_event.wait(5)
            return True

        # Acquire or renew poll lock
        if not self._acquire_or_renew_lock():
            logger.debug("Bot %s poll lock held by another instance, skipping iteration.", self.bot_id)
            self.stop_event.wait(3)
            return True

        offset = (bot.last_update_id + 1) if bot.last_update_id else None
        res: dict[str, Any] = self.client.get_updates(token, offset=offset, timeout=20)

        if res.get("ok") and "result" in res:
            self._error_streak = 0
            updates = res["result"]
            highest_id = bot.last_update_id
            for update in updates:
                if self.stop_event.is_set():
                    break
                # Продовжуємо TTL блокування перед кожним update на випадок довгих відповідей LLM.
                if not self._acquire_or_renew_lock():
                    logger.warning(
                        "Bot %s lost poll lock mid-batch, stopping batch cleanly.",
                        self.bot_id,
                    )
                    break
                try:
                    handle_telegram_update(bot, update, client=self.client)
                except Exception as exc:
                    logger.exception("Error handling update in bot %s: %s", self.bot_id, exc)
                uid = update.get("update_id")
                if uid is not None and uid > highest_id:
                    highest_id = uid
                    bot.last_update_id = highest_id
                    bot.last_poll_at = timezone.now()
                    bot.last_error = ""
                    bot.save(
                        update_fields=["last_update_id", "last_poll_at", "last_error", "updated_at"],
                    )

            if not updates:
                bot.last_poll_at = timezone.now()
                bot.last_error = ""
                bot.save(update_fields=["last_poll_at", "last_error", "updated_at"])
        else:
            err = res.get("description", "Помилка запиту до Telegram API")
            bot.last_error = err
            bot.save(update_fields=["last_error", "updated_at"])
            retry_after = (res.get("parameters") or {}).get("retry_after")
            try:
                retry_sec = float(retry_after) if retry_after is not None else 0.0
            except (TypeError, ValueError):
                retry_sec = 0.0
            if retry_sec > 0:
                self._error_streak = 0
                wait_sec = min(retry_sec, 60.0)
            else:
                self._error_streak += 1
                wait_sec = min(5 * (2 ** (self._error_streak - 1)), 60)
            self.stop_event.wait(wait_sec)

        return True

    def run(self) -> None:
        """Worker main loop."""
        logger.info("Starting worker loop for bot %s", self.bot_id)
        while not self.stop_event.is_set():
            try:
                should_continue = self.step()
                if not should_continue:
                    break
            except Exception as exc:
                logger.exception("Unexpected error in worker loop for bot %s: %s", self.bot_id, exc)
                self.stop_event.wait(5)
            finally:
                from django.db import connection

                connection.close_if_unusable_or_obsolete()

        self._release_lock()
        logger.info("Exited worker loop for bot %s", self.bot_id)


class TelegramBotManager:
    """Manager for orchestrating long polling workers for all active bots."""

    def __init__(self, client: TelegramClient | None = None):
        self._shared_client = client
        self.workers: dict[int, tuple[TelegramBotWorker, threading.Event, str]] = {}
        self._stopped = False

    def _touch_heartbeat(self) -> None:
        try:
            HEARTBEAT_PATH.write_text(str(time.time()), encoding="utf-8")
        except OSError as exc:
            logger.debug("Failed to write poller heartbeat %s: %s", HEARTBEAT_PATH, exc)

    def sync_bots(self) -> None:
        """Synchronize running worker threads with active bots in DB."""
        active_bots = TelegramBot.objects.filter(
            is_active=True,
            workspace__isnull=False,
        ).select_related("workspace")
        active_bot_map = {bot.id: bot for bot in active_bots}

        # 1. Stop workers for bots that became inactive, deleted, or changed token
        for bot_id in list(self.workers.keys()):
            worker, stop_event, token_hash = self.workers[bot_id]
            bot = active_bot_map.get(bot_id)
            if not bot or not worker.is_alive() or bot.encrypted_token != token_hash:
                stop_event.set()
                if worker.ident is not None:
                    worker.join(timeout=2.0)
                del self.workers[bot_id]

        # 2. Start workers for newly active bots
        if not self._stopped:
            for bot_id, bot in active_bot_map.items():
                if bot_id not in self.workers:
                    stop_event = threading.Event()
                    worker = TelegramBotWorker(
                        bot_id=bot.id,
                        stop_event=stop_event,
                        client=self._shared_client or TelegramClient(),
                    )
                    worker.start()
                    self.workers[bot_id] = (worker, stop_event, bot.encrypted_token)

    def run(self, poll_interval: float = 5.0) -> None:
        """Periodically sync active bots."""
        logger.info("TelegramBotManager daemon running.")
        while not self._stopped:
            try:
                self.sync_bots()
                self._touch_heartbeat()
            except Exception as exc:
                logger.exception("Error during bot sync: %s", exc)
            finally:
                from django.db import connection

                connection.close_if_unusable_or_obsolete()

            deadline = time.monotonic() + poll_interval
            while not self._stopped and time.monotonic() < deadline:
                time.sleep(0.2)

        self.stop()
        logger.info("TelegramBotManager daemon stopped.")

    def stop(self) -> None:
        """Stop all running worker threads."""
        self._stopped = True
        for worker, stop_event, _ in list(self.workers.values()):
            stop_event.set()
            if worker.ident is not None:
                worker.join(timeout=2.0)
        self.workers.clear()
