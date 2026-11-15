"""Serializers for Telegram bot integration."""
import logging

from rest_framework import serializers

from workspaces.models import TelegramBot
from workspaces.telegram.client import TelegramClient

logger = logging.getLogger(__name__)


def _apply_and_verify_token(bot: TelegramBot, token: str) -> None:
    """Зашифрувати токен і перевірити профіль бота через Telegram getMe."""
    bot.set_token(token)
    try:
        me = TelegramClient().get_me(token)
    except Exception as exc:
        logger.warning('Unexpected error verifying Telegram token: %s', exc, exc_info=True)
        bot.last_error = str(exc) or 'Не вдалося перевірити токен'
        return

    if isinstance(me, dict) and me.get('ok') and isinstance(me.get('result'), dict):
        bot.bot_username = me['result'].get('username') or ''
        bot.last_error = ''
    elif isinstance(me, dict) and me.get('ok'):
        bot.last_error = 'Некоректна відповідь Telegram API'
    elif isinstance(me, dict):
        bot.last_error = me.get('description') or 'Не вдалося перевірити токен'
    else:
        bot.last_error = 'Некоректна відповідь Telegram API'


class TelegramBotSerializer(serializers.ModelSerializer):
    token = serializers.CharField(write_only=True, required=False, allow_blank=True)
    token_masked = serializers.CharField(read_only=True)
    has_token = serializers.SerializerMethodField()
    workspace_name = serializers.CharField(source='workspace.name', read_only=True)

    class Meta:
        model = TelegramBot
        fields = (
            'id',
            'name',
            'token',
            'token_masked',
            'has_token',
            'bot_username',
            'workspace',
            'workspace_name',
            'is_active',
            'last_poll_at',
            'last_error',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('last_poll_at', 'last_error', 'created_at', 'updated_at')

    def get_has_token(self, obj: TelegramBot) -> bool:
        return bool(obj.encrypted_token)

    def create(self, validated_data):
        token = validated_data.pop('token', None)
        bot = TelegramBot(**validated_data)
        if token:
            _apply_and_verify_token(bot, token)
        bot.save()
        return bot

    def update(self, instance, validated_data):
        token = validated_data.pop('token', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if token:
            _apply_and_verify_token(instance, token)
        instance.save()
        return instance
