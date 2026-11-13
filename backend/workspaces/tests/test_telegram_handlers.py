"""Tests for Telegram Update handlers."""
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework.response import Response

from chats.models import WorkspaceChatLog
from workspaces.models import TelegramBot, TelegramChatSession, Workspace
from workspaces.telegram.handlers import handle_telegram_update


class TelegramHandlerTests(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(
            name="Підтримка Студентів",
            embed_greeting="Привіт! Чим можу допомогти?",
            embed_faq_questions=["Розклад занять", "Як отримати довідку?"],
            model_names=["llama3"],
        )
        self.bot = TelegramBot.objects.create(
            name="HelpBot",
            workspace=self.workspace,
            bot_username="help_bot",
        )
        self.bot.set_token("123456:SECRET")
        self.bot.save()
        self.client_mock = MagicMock()

    def test_unassigned_bot_reply(self):
        unassigned_bot = TelegramBot.objects.create(name="OrphanBot")
        unassigned_bot.set_token("999999:SECRET")
        unassigned_bot.save()

        update = {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 12345},
                "from": {"id": 12345, "username": "user1"},
                "text": "Привіт",
            },
        }

        handle_telegram_update(unassigned_bot, update, client=self.client_mock)
        self.client_mock.send_message.assert_called_once()
        args, kwargs = self.client_mock.send_message.call_args
        self.assertIn("налаштовується", kwargs.get("text", "") or args[2])

    def test_start_command_resets_session_and_sends_greeting_with_faq(self):
        # Pre-existing session with messages
        session = TelegramChatSession.objects.create(
            bot=self.bot,
            telegram_chat_id=12345,
            telegram_username="user1",
            messages=[{"role": "user", "content": "попереднє повідомлення"}],
        )

        update = {
            "update_id": 2,
            "message": {
                "message_id": 11,
                "chat": {"id": 12345},
                "from": {"id": 12345, "username": "user1"},
                "text": "/start",
            },
        }

        handle_telegram_update(self.bot, update, client=self.client_mock)

        session.refresh_from_db()
        self.assertEqual(session.messages, [])

        self.client_mock.send_message.assert_called_once()
        args, kwargs = self.client_mock.send_message.call_args
        sent_text = kwargs.get("text") or args[2]
        self.assertEqual(sent_text, "Привіт! Чим можу допомогти?")

        markup = kwargs.get("reply_markup")
        self.assertIsNotNone(markup)
        inline_kb = markup["inline_keyboard"]
        self.assertEqual(len(inline_kb), 2)
        self.assertEqual(inline_kb[0][0]["text"], "Розклад занять")
        self.assertEqual(inline_kb[0][0]["callback_data"], "faq:0")
        self.assertEqual(inline_kb[1][0]["text"], "Як отримати довідку?")
        self.assertEqual(inline_kb[1][0]["callback_data"], "faq:1")

    def test_reset_command_clears_session(self):
        session = TelegramChatSession.objects.create(
            bot=self.bot,
            telegram_chat_id=12345,
            telegram_username="user1",
            messages=[{"role": "user", "content": "hello"}],
        )

        update = {
            "update_id": 3,
            "message": {
                "message_id": 12,
                "chat": {"id": 12345},
                "from": {"id": 12345, "username": "user1"},
                "text": "/reset",
            },
        }

        handle_telegram_update(self.bot, update, client=self.client_mock)
        session.refresh_from_db()
        self.assertEqual(session.messages, [])
        self.client_mock.send_message.assert_called_once()

    @patch("workspaces.telegram.handlers.run_chat")
    def test_text_message_calls_run_chat_and_saves_history_and_feedback(self, mock_run_chat):
        log = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            prompt="Де знайти розклад?",
            response="Розклад знаходиться на сайті університету.",
        )
        mock_run_chat.return_value = Response(
            {
                "message": {"content": "Розклад знаходиться на сайті університету."},
                "log_id": log.id,
            },
            status=200,
        )

        update = {
            "update_id": 4,
            "message": {
                "message_id": 13,
                "chat": {"id": 12345},
                "from": {"id": 12345, "username": "student"},
                "text": "Де знайти розклад?",
            },
        }

        handle_telegram_update(self.bot, update, client=self.client_mock)

        # Verified typing indicator
        self.client_mock.send_chat_action.assert_called_once_with(
            "123456:SECRET",
            12345,
            action="typing",
        )

        # Verified run_chat call
        mock_run_chat.assert_called_once()
        _, rkwargs = mock_run_chat.call_args
        self.assertEqual(rkwargs["model"], "llama3")
        self.assertEqual(rkwargs["prompt"], "Де знайти розклад?")
        self.assertEqual(rkwargs["workspace"], self.workspace)
        self.assertEqual(
            rkwargs["messages"],
            [{"role": "user", "content": "Де знайти розклад?"}],
        )

        # Verified session history updated
        session = TelegramChatSession.objects.get(bot=self.bot, telegram_chat_id=12345)
        self.assertEqual(len(session.messages), 2)
        self.assertEqual(session.messages[0], {"role": "user", "content": "Де знайти розклад?"})
        self.assertEqual(
            session.messages[1],
            {"role": "assistant", "content": "Розклад знаходиться на сайті університету."},
        )

        # Verified message sent with feedback buttons
        self.client_mock.send_message.assert_called_once()
        args, sm_kwargs = self.client_mock.send_message.call_args
        msg_text = sm_kwargs.get("text") or (args[2] if len(args) > 2 else "")
        self.assertEqual(msg_text, "Розклад знаходиться на сайті університету.")
        markup = sm_kwargs.get("reply_markup") or (args[3] if len(args) > 3 else None)
        self.assertIsNotNone(markup)
        kb = markup["inline_keyboard"][0]
        self.assertEqual(kb[0]["callback_data"], f"fb:{log.id}:up")
        self.assertEqual(kb[1]["callback_data"], f"fb:{log.id}:down")
        self.assertEqual(kb[2]["callback_data"], f"fb:{log.id}:handoff")

    @patch("workspaces.telegram.handlers.run_chat")
    def test_text_message_error_response(self, mock_run_chat):
        mock_run_chat.return_value = Response(
            {"error": "Сервер перевантажений, спробуйте пізніше."},
            status=429,
        )

        update = {
            "update_id": 5,
            "message": {
                "message_id": 14,
                "chat": {"id": 12345},
                "from": {"id": 12345, "username": "student"},
                "text": "Тест помилки",
            },
        }

        handle_telegram_update(self.bot, update, client=self.client_mock)
        self.client_mock.send_message.assert_called_once()
        args, kwargs = self.client_mock.send_message.call_args
        msg_text = kwargs.get("text") or (args[2] if len(args) > 2 else "")
        self.assertIn("перевантажений", msg_text)

    def test_feedback_callback_up(self):
        log = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            prompt="Питання",
            response="Відповідь",
        )

        update = {
            "update_id": 6,
            "callback_query": {
                "id": "cq_up_1",
                "from": {"id": 12345, "username": "student"},
                "message": {"message_id": 100, "chat": {"id": 12345}},
                "data": f"fb:{log.id}:up",
            },
        }

        handle_telegram_update(self.bot, update, client=self.client_mock)

        log.refresh_from_db()
        self.assertEqual(log.feedback, "up")
        self.assertFalse(log.needs_handoff)

        self.client_mock.answer_callback_query.assert_called_once_with(
            "123456:SECRET",
            "cq_up_1",
            text="Дякуємо за відгук!",
        )
        self.client_mock.edit_message_reply_markup.assert_called_once_with(
            "123456:SECRET",
            12345,
            100,
            reply_markup={"inline_keyboard": []},
        )

    def test_feedback_callback_handoff(self):
        log = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            prompt="Складне питання",
            response="Не знаю",
        )

        update = {
            "update_id": 7,
            "callback_query": {
                "id": "cq_ho_1",
                "from": {"id": 12345, "username": "student"},
                "message": {"message_id": 101, "chat": {"id": 12345}},
                "data": f"fb:{log.id}:handoff",
            },
        }

        handle_telegram_update(self.bot, update, client=self.client_mock)

        log.refresh_from_db()
        self.assertTrue(log.needs_handoff)

        self.client_mock.answer_callback_query.assert_called_once_with(
            "123456:SECRET",
            "cq_ho_1",
            text="Запит передано фахівцю!",
        )
        self.client_mock.edit_message_reply_markup.assert_called_once_with(
            "123456:SECRET",
            12345,
            101,
            reply_markup={"inline_keyboard": []},
        )

    @patch("workspaces.telegram.handlers.run_chat")
    def test_faq_callback_query(self, mock_run_chat):
        mock_run_chat.return_value = Response(
            {
                "response": "Розклад занять: понеділок-п'ятниця 9:00 - 16:00.",
                "log_id": 99,
            },
            status=200,
        )

        update = {
            "update_id": 8,
            "callback_query": {
                "id": "cq_faq_0",
                "from": {"id": 12345, "username": "student"},
                "message": {"message_id": 102, "chat": {"id": 12345}},
                "data": "faq:0",
            },
        }

        handle_telegram_update(self.bot, update, client=self.client_mock)

        self.client_mock.answer_callback_query.assert_called_once_with(
            "123456:SECRET",
            "cq_faq_0",
        )
        mock_run_chat.assert_called_once()
        _, rkwargs = mock_run_chat.call_args
        self.assertEqual(rkwargs["prompt"], "Розклад занять")
