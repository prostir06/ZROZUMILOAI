"""Views for Telegram bot management."""
import logging

from django.db import DatabaseError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from workspaces.models import TelegramBot
from workspaces.telegram.client import TelegramClient
from workspaces.telegram.serializers import TelegramBotSerializer

logger = logging.getLogger(__name__)


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

        try:
            res = TelegramClient().get_me(token)
        except Exception as exc:
            logger.warning('Unexpected error verifying bot %s: %s', bot.id, exc, exc_info=True)
            res = {'ok': False, 'description': str(exc) or 'Помилка мережі Telegram'}

        if isinstance(res, dict) and res.get('ok') and isinstance(res.get('result'), dict):
            bot.bot_username = res['result'].get('username') or ''
            bot.last_error = ''
            try:
                bot.save(update_fields=['bot_username', 'last_error', 'updated_at'])
            except DatabaseError as exc:
                logger.exception('Failed to save verified bot %s: %s', bot.id, exc)
                return Response(
                    {'error': 'Не вдалося зберегти статус бота'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            return Response(self.get_serializer(bot).data)

        if isinstance(res, dict) and res.get('ok'):
            error_msg = 'Некоректна відповідь Telegram API'
        else:
            error_msg = (
                (res.get('description') if isinstance(res, dict) else None)
                or 'Невалідний токен або помилка мережі Telegram'
            )

        bot.last_error = error_msg
        try:
            bot.save(update_fields=['last_error', 'updated_at'])
        except DatabaseError as exc:
            logger.exception('Failed to save bot %s verification error: %s', bot.id, exc)
            return Response(
                {'error': 'Не вдалося зберегти статус бота'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
