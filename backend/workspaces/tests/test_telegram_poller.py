"""Tests for Telegram Poller Worker and Manager."""
import threading
from unittest.mock import MagicMock, patch

from django.test import TransactionTestCase

from workspaces.models import TelegramBot, Workspace
from workspaces.telegram.poller import TelegramBotManager, TelegramBotWorker


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
