"""Tests for TelegramBot and TelegramChatSession models."""
from django.db import IntegrityError
from django.test import TestCase

from workspaces.models import TelegramBot, TelegramChatSession, Workspace


class TelegramModelTests(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(name='Telegram Test WS')

    def test_token_encryption_and_masking(self):
        bot = TelegramBot(name='Support Bot', workspace=self.workspace)
        raw_token = '123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234'
        bot.set_token(raw_token)
        bot.save()

        # In DB, token must be encrypted
        bot.refresh_from_db()
        self.assertTrue(bot.encrypted_token.startswith('enc:v1:'))
        self.assertEqual(bot.get_token(), raw_token)
        self.assertEqual(bot.token_masked, '123456789:***1234')

    def test_token_masking_short_or_empty(self):
        bot = TelegramBot(name='Empty Token Bot')
        self.assertEqual(bot.token_masked, '')

        bot.set_token('short')
        self.assertEqual(bot.token_masked, '***')

    def test_chat_session_unique_constraint_and_messages(self):
        bot = TelegramBot.objects.create(name='Chat Bot', workspace=self.workspace)
        session = TelegramChatSession.objects.create(
            bot=bot,
            telegram_chat_id=987654321,
            telegram_username='student_ua',
            messages=[{'role': 'user', 'content': 'Привіт!'}],
        )
        self.assertEqual(session.messages[0]['content'], 'Привіт!')

        with self.assertRaises(IntegrityError):
            TelegramChatSession.objects.create(
                bot=bot,
                telegram_chat_id=987654321,
            )
