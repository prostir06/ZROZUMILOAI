"""Tests for Telegram API client."""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from workspaces.telegram.client import TelegramClient


class TelegramClientTests(TestCase):
    def setUp(self):
        self.client = TelegramClient(base_url="https://api.telegram.org")
        self.token = "123456:ABCdefGHI"

    @patch("requests.Session.get")
    def test_get_me_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "ok": True,
            "result": {"id": 123456, "is_bot": True, "username": "test_bot"},
        }
        mock_get.return_value = mock_resp

        res = self.client.get_me(self.token)
        self.assertTrue(res.get("ok"))
        self.assertEqual(res["result"]["username"], "test_bot")
        mock_get.assert_called_once_with(
            "https://api.telegram.org/bot123456:ABCdefGHI/getMe",
            timeout=5,
        )

    @patch("requests.Session.get")
    def test_get_me_failure(self, mock_get):
        mock_get.side_effect = Exception("Connection timeout")

        res = self.client.get_me(self.token)
        self.assertFalse(res.get("ok"))
        self.assertIn("Connection timeout", res.get("description", ""))

    @patch("requests.Session.get")
    def test_get_updates(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "ok": True,
            "result": [{"update_id": 100, "message": {"text": "hi"}}],
        }
        mock_get.return_value = mock_resp

        res = self.client.get_updates(self.token, offset=100, timeout=20)
        self.assertTrue(res.get("ok"))
        self.assertEqual(len(res["result"]), 1)
        mock_get.assert_called_once_with(
            "https://api.telegram.org/bot123456:ABCdefGHI/getUpdates",
            params={"offset": 100, "timeout": 20},
            timeout=30,
        )

    @patch("requests.Session.post")
    def test_send_message_short(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True, "result": {"message_id": 1}}
        mock_post.return_value = mock_resp

        markup = {"inline_keyboard": [[{"text": "Btn", "callback_data": "btn"}]]}
        res = self.client.send_message(
            self.token,
            chat_id=987654,
            text="Привіт світ!",
            reply_markup=markup,
        )
        self.assertTrue(res.get("ok"))
        mock_post.assert_called_once_with(
            "https://api.telegram.org/bot123456:ABCdefGHI/sendMessage",
            json={
                "chat_id": 987654,
                "text": "Привіт світ!",
                "reply_markup": markup,
            },
            timeout=10,
        )

    @patch("requests.Session.post")
    def test_send_message_chunking(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True, "result": {"message_id": 1}}
        mock_post.return_value = mock_resp

        long_text = "A" * 9500
        markup = {"inline_keyboard": [[{"text": "Like", "callback_data": "up"}]]}

        res = self.client.send_message(
            self.token,
            chat_id=987654,
            text=long_text,
            reply_markup=markup,
        )
        self.assertTrue(res.get("ok"))
        self.assertEqual(mock_post.call_count, 3)

        calls = mock_post.call_args_list
        # First chunk: 4000 chars, no markup
        self.assertEqual(len(calls[0].kwargs["json"]["text"]), 4000)
        self.assertNotIn("reply_markup", calls[0].kwargs["json"])

        # Second chunk: 4000 chars, no markup
        self.assertEqual(len(calls[1].kwargs["json"]["text"]), 4000)
        self.assertNotIn("reply_markup", calls[1].kwargs["json"])

        # Third chunk: 1500 chars, with markup
        self.assertEqual(len(calls[2].kwargs["json"]["text"]), 1500)
        self.assertEqual(calls[2].kwargs["json"]["reply_markup"], markup)

    @patch("requests.Session.post")
    def test_send_chat_action(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True, "result": True}
        mock_post.return_value = mock_resp

        res = self.client.send_chat_action(self.token, chat_id=123, action="typing")
        self.assertTrue(res.get("ok"))
        mock_post.assert_called_once_with(
            "https://api.telegram.org/bot123456:ABCdefGHI/sendChatAction",
            json={"chat_id": 123, "action": "typing"},
            timeout=5,
        )

    @patch("requests.Session.post")
    def test_answer_callback_query(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True, "result": True}
        mock_post.return_value = mock_resp

        res = self.client.answer_callback_query(
            self.token,
            callback_query_id="cq123",
            text="Дякуємо!",
            show_alert=False,
        )
        self.assertTrue(res.get("ok"))
        mock_post.assert_called_once_with(
            "https://api.telegram.org/bot123456:ABCdefGHI/answerCallbackQuery",
            json={"callback_query_id": "cq123", "text": "Дякуємо!", "show_alert": False},
            timeout=5,
        )

    @patch("requests.Session.get")
    def test_non_json_http_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        mock_resp.text = "<html><body>502 Bad Gateway</body></html>"
        mock_resp.json.side_effect = ValueError("No JSON object could be decoded")
        mock_get.return_value = mock_resp

        res = self.client.get_me(self.token)
        self.assertFalse(res.get("ok"))
        self.assertIn("HTTP 502", res.get("description", ""))
        self.assertIn("Bad Gateway", res.get("description", ""))

    @patch("requests.Session.post")
    def test_send_message_chunk_failure(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"ok": False, "description": "Bad Request: chat not found"}
        mock_post.return_value = mock_resp

        res = self.client.send_message(self.token, chat_id=123, text="A" * 9000)
        self.assertFalse(res.get("ok"))
        # Should abort on first chunk failure
        self.assertEqual(mock_post.call_count, 1)

    @patch("requests.Session.post")
    def test_edit_message_reply_markup(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True, "result": {"message_id": 5}}
        mock_post.return_value = mock_resp

        res = self.client.edit_message_reply_markup(
            self.token,
            chat_id=123,
            message_id=5,
            reply_markup={"inline_keyboard": []},
        )
        self.assertTrue(res.get("ok"))
        mock_post.assert_called_once_with(
            "https://api.telegram.org/bot123456:ABCdefGHI/editMessageReplyMarkup",
            json={
                "chat_id": 123,
                "message_id": 5,
                "reply_markup": {"inline_keyboard": []},
            },
            timeout=5,
        )
