"""Serializers for Telegram bot integration."""
from rest_framework import serializers

from workspaces.models import TelegramBot


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
            bot.set_token(token)
            from workspaces.telegram.client import TelegramClient

            me = TelegramClient().get_me(token)
            if me.get('ok') and 'result' in me:
                bot.bot_username = me['result'].get('username', '')
                bot.last_error = ''
            elif not me.get('ok'):
                bot.last_error = me.get('description', 'Не вдалося перевірити токен')
        bot.save()
        return bot

    def update(self, instance, validated_data):
        token = validated_data.pop('token', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if token:
            instance.set_token(token)
            from workspaces.telegram.client import TelegramClient

            me = TelegramClient().get_me(token)
            if me.get('ok') and 'result' in me:
                instance.bot_username = me['result'].get('username', '')
                instance.last_error = ''
            elif not me.get('ok'):
                instance.last_error = me.get('description', 'Не вдалося перевірити токен')
        instance.save()
        return instance
