from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from workspaces.models import TelegramBot, Workspace

User = get_user_model()


class TelegramBotAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')
        self.regular_user = User.objects.create_user('user', 'user@example.com', 'userpass')
        self.workspace = Workspace.objects.create(name='Main WS')
        self.client.force_authenticate(user=self.admin)

    def test_anonymous_and_regular_user_forbidden(self):
        self.client.logout()
        res = self.client.get('/api/telegram-bots/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=self.regular_user)
        res = self.client.get('/api/telegram-bots/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    @patch('workspaces.telegram.client.TelegramClient.get_me')
    def test_create_and_list_telegram_bot(self, mock_get_me):
        mock_get_me.return_value = {'ok': True, 'result': {'username': 'zrozumilo_bot'}}

        payload = {
            'name': 'Довідка',
            'token': '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11',
            'workspace': self.workspace.id,
            'is_active': True,
        }
        res = self.client.post('/api/telegram-bots/', payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['bot_username'], 'zrozumilo_bot')
        self.assertEqual(res.data['token_masked'], '123456:***ew11')
        self.assertNotIn('token', res.data)

        # Check list
        list_res = self.client.get('/api/telegram-bots/')
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]['name'], 'Довідка')
        self.assertEqual(list_res.data[0]['workspace_name'], 'Main WS')

    @patch('workspaces.telegram.client.TelegramClient.get_me')
    def test_verify_token_endpoint(self, mock_get_me):
        mock_get_me.return_value = {'ok': True, 'result': {'username': 'verified_bot'}}
        bot = TelegramBot(name='Bot 1', workspace=self.workspace)
        bot.set_token('12345:validtoken123456789')
        bot.save()

        res = self.client.post(f'/api/telegram-bots/{bot.id}/verify/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        bot.refresh_from_db()
        self.assertEqual(bot.bot_username, 'verified_bot')
        self.assertEqual(bot.last_error, '')

    def test_workspace_serializer_syncs_telegram_bot_ids(self):
        bot1 = TelegramBot.objects.create(name='Bot 1')
        bot2 = TelegramBot.objects.create(name='Bot 2')

        # Link both bots via workspace update
        ws_res = self.client.patch(
            f'/api/workspaces/{self.workspace.id}/',
            {'telegram_bot_ids': [bot1.id, bot2.id]},
            format='json',
        )
        self.assertEqual(ws_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(ws_res.data.get('telegram_bots', [])), 2)

        bot1.refresh_from_db()
        bot2.refresh_from_db()
        self.assertEqual(bot1.workspace_id, self.workspace.id)
        self.assertEqual(bot2.workspace_id, self.workspace.id)

        # Remove bot1 by passing only bot2
        self.client.patch(
            f'/api/workspaces/{self.workspace.id}/',
            {'telegram_bot_ids': [bot2.id]},
            format='json',
        )
        bot1.refresh_from_db()
        bot2.refresh_from_db()
        self.assertIsNone(bot1.workspace)
        self.assertEqual(bot2.workspace_id, self.workspace.id)
