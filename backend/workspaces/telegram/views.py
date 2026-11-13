"""Views for Telegram bot management."""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from workspaces.models import TelegramBot
from workspaces.telegram.client import TelegramClient
from workspaces.telegram.serializers import TelegramBotSerializer


class TelegramBotViewSet(viewsets.ModelViewSet):
    queryset = TelegramBot.objects.select_related('workspace').all()
    serializer_class = TelegramBotSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        bot = self.get_object()
        token = bot.get_token()
        if not token:
            return Response(
                {'error': 'Токен відсутній'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        res = TelegramClient().get_me(token)
        if res.get('ok') and 'result' in res:
            bot.bot_username = res['result'].get('username', '')
            bot.last_error = ''
            bot.save(update_fields=['bot_username', 'last_error', 'updated_at'])
            return Response(self.get_serializer(bot).data)

        error_msg = res.get('description') or 'Невалідний токен або помилка мережі Telegram'
        bot.last_error = error_msg
        bot.save(update_fields=['last_error', 'updated_at'])
        return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
