"""Tests for Telegram Poller Worker and Manager."""
import threading
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TransactionTestCase, override_settings

from workspaces.models import TelegramBot, Workspace
from workspaces.telegram.poller import (
    TELEGRAM_POLLER_HEARTBEAT_CACHE_KEY,
    TelegramBotManager,
    TelegramBotWorker,
)


class TelegramPollerTests(TransactionTestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(
            name="WS Poller",
            model_names=["llama3"],
        )
        self.bot = TelegramBot.objects.create(
            name="PollerBot",
            workspace=self.workspace,
            is_active=True,
        )
        self.bot.set_token("111222:SECRET")
        self.bot.save()
        self.client_mock = MagicMock()
        self.client_mock.get_updates.return_value = {"ok": True, "result": []}

    @patch("workspaces.telegram.poller.handle_telegram_update")
    def test_worker_polls_and_updates_last_update_id(self, mock_handle):
        stop_event = threading.Event()

        def fake_get_updates(token, offset=None, timeout=20):
            return {
                "ok": True,
                "result": [{"update_id": 42, "message": {"text": "hello"}}],
            }

        self.client_mock.get_updates.side_effect = fake_get_updates

        worker = TelegramBotWorker(
            bot_id=self.bot.id,
            stop_event=stop_event,
            client=self.client_mock,
        )
        # Run one iteration synchronously to test logic directly
        worker.step()

        self.bot.refresh_from_db()
        self.assertEqual(self.bot.last_update_id, 42)
        self.assertIsNotNone(self.bot.last_poll_at)
        self.assertEqual(self.bot.last_error, "")
        mock_handle.assert_called_once()

    def test_worker_handles_telegram_error(self):
        self.client_mock.get_updates.return_value = {
            "ok": False,
            "description": "Unauthorized token",
        }

        worker = TelegramBotWorker(
            bot_id=self.bot.id,
            client=self.client_mock,
        )
        worker.step()

        self.bot.refresh_from_db()
        self.assertEqual(self.bot.last_error, "Unauthorized token")

    def test_manager_sync_bots_spawns_and_stops_threads(self):
        manager = TelegramBotManager(client=self.client_mock)

        # 1. Sync starts active bot worker
        manager.sync_bots()
        self.assertIn(self.bot.id, manager.workers)
        worker_tuple = manager.workers[self.bot.id]
        worker, stop_event, _ = worker_tuple
        self.assertTrue(worker.is_alive())

        # 2. Deactivating bot stops worker
        self.bot.is_active = False
        self.bot.save()

        manager.sync_bots()
        self.assertNotIn(self.bot.id, manager.workers)
        self.assertTrue(stop_event.is_set())

        # Clean up
        manager.stop()

    def test_manager_stop_stops_all_workers(self):
        manager = TelegramBotManager(client=self.client_mock)
        manager.sync_bots()
        self.assertIn(self.bot.id, manager.workers)

        manager.stop()
        self.assertEqual(len(manager.workers), 0)

    @override_settings(REDIS_URL="redis://localhost:6379/0")
    @patch("workspaces.telegram.poller._get_redis_client")
    def test_worker_skips_polling_when_redis_fails_and_redis_url_set(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.eval.side_effect = ConnectionError("redis down")
        mock_get_redis.return_value = mock_redis

        worker = TelegramBotWorker(
            bot_id=self.bot.id,
            client=self.client_mock,
        )

        self.assertFalse(worker._acquire_or_renew_lock())
        worker.step()
        self.client_mock.get_updates.assert_not_called()

    @override_settings(REDIS_URL="")
    def test_worker_polls_when_redis_url_empty(self):
        worker = TelegramBotWorker(
            bot_id=self.bot.id,
            client=self.client_mock,
        )
        self.assertTrue(worker._acquire_or_renew_lock())

    @override_settings(REDIS_URL="redis://localhost:6379/0")
    @patch("workspaces.telegram.poller._get_redis_client", return_value=None)
    def test_worker_skips_polling_when_redis_client_none_and_redis_url_set(self, _mock_get_redis):
        worker = TelegramBotWorker(
            bot_id=self.bot.id,
            client=self.client_mock,
        )
        self.assertFalse(worker._acquire_or_renew_lock())
        worker.step()
        self.client_mock.get_updates.assert_not_called()

    @override_settings(REDIS_URL="redis://localhost:6379/0")
    @patch("workspaces.telegram.poller._get_redis_client")
    @patch("workspaces.telegram.poller.handle_telegram_update")
    def test_worker_persists_each_update_id_and_renews_lock_mid_batch(
        self,
        mock_handle,
        mock_get_redis,
    ):
        mock_redis = MagicMock()
        mock_redis.eval.return_value = 1
        mock_get_redis.return_value = mock_redis

        self.client_mock.get_updates.return_value = {
            "ok": True,
            "result": [
                {"update_id": 50, "message": {"text": "one"}},
                {"update_id": 51, "message": {"text": "two"}},
            ],
        }
        worker = TelegramBotWorker(bot_id=self.bot.id, client=self.client_mock)
        worker.step()

        self.bot.refresh_from_db()
        self.assertEqual(self.bot.last_update_id, 51)
        self.assertEqual(mock_handle.call_count, 2)
        # 1 initial lock + 2 renewals before each update
        self.assertEqual(mock_redis.eval.call_count, 3)

    def test_worker_respects_retry_after_and_exponential_backoff(self):
        stop_event = MagicMock()
        stop_event.is_set.return_value = False
        self.client_mock.get_updates.return_value = {
            "ok": False,
            "description": "Too Many Requests",
            "parameters": {"retry_after": 12},
        }
        worker = TelegramBotWorker(
            bot_id=self.bot.id,
            stop_event=stop_event,
            client=self.client_mock,
        )
        worker.step()
        stop_event.wait.assert_called_once_with(12.0)

        stop_event.reset_mock()
        self.client_mock.get_updates.return_value = {
            "ok": False,
            "description": "Network glitch",
        }
        worker.step()
        worker.step()
        self.assertEqual(stop_event.wait.call_args_list[0].args[0], 5)
        self.assertEqual(stop_event.wait.call_args_list[1].args[0], 10)

    def test_manager_gives_each_worker_isolated_client_when_unshared(self):
        bot2 = TelegramBot.objects.create(
            name="PollerBot2",
            workspace=self.workspace,
            is_active=True,
        )
        bot2.set_token("333444:SECRET2")
        bot2.save()

        manager = TelegramBotManager()
        with patch.object(TelegramBotWorker, "start"):
            manager.sync_bots()
            w1 = manager.workers[self.bot.id][0]
            w2 = manager.workers[bot2.id][0]
            self.assertIsNot(w1.client, w2.client)
            self.assertIsNot(w1.client.session, w2.client.session)
        manager.stop()

    def test_touch_heartbeat_publishes_timestamp_to_cache(self):
        cache.delete(TELEGRAM_POLLER_HEARTBEAT_CACHE_KEY)
        manager = TelegramBotManager(client=self.client_mock)
        manager._touch_heartbeat()
        cached_ts = cache.get(TELEGRAM_POLLER_HEARTBEAT_CACHE_KEY)
        self.assertIsNotNone(cached_ts)
        self.assertGreater(float(cached_ts), 0.0)


