"""Telegram Long Polling daemon and worker threads."""
import logging
import threading
import time
import uuid
from typing import Any

from django.conf import settings
from django.utils import timezone

from workspaces.models import TelegramBot
from workspaces.telegram.client import TelegramClient
from workspaces.telegram.handlers import handle_telegram_update

logger = logging.getLogger(__name__)

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

    def _acquire_or_renew_lock(self) -> bool:
        redis_client = _get_redis_client()
        if redis_client is None:
            return True

        key = f"telegram:poll_lock:{self.bot_id}"
        try:
            res = redis_client.eval(_RENEW_OR_ACQUIRE_LUA, 1, key, self.lock_token, 60)
            return bool(res)
        except Exception as exc:
            logger.warning("Redis error acquiring poll lock for bot %s (failing open): %s", self.bot_id, exc)
            return True

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
            updates = res["result"]
            highest_id = bot.last_update_id
            for update in updates:
                if self.stop_event.is_set():
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
            bot.save(update_fields=["last_update_id", "last_poll_at", "last_error", "updated_at"])
        else:
            err = res.get("description", "Помилка запиту до Telegram API")
            bot.last_error = err
            bot.save(update_fields=["last_error", "updated_at"])
            self.stop_event.wait(5)

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
        self.client = client or TelegramClient()
        self.workers: dict[int, tuple[TelegramBotWorker, threading.Event, str]] = {}
        self._stopped = False

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
                        client=self.client,
                    )
                    worker.start()
                    self.workers[bot_id] = (worker, stop_event, bot.encrypted_token)

    def run(self, poll_interval: float = 5.0) -> None:
        """Periodically sync active bots."""
        logger.info("TelegramBotManager daemon running.")
        while not self._stopped:
            try:
                self.sync_bots()
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
            worker.join(timeout=2.0)
        self.workers.clear()
