"""Management command to run dynamic long polling daemon for active Telegram bots."""
import logging
import signal
import sys

from django.core.management.base import BaseCommand

from workspaces.telegram.poller import TelegramBotManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Run dynamic long polling daemon for active Telegram bots."""

    help = "Запуск фонового сервісу Long Polling для Телеграм-ботів"

    def handle(self, *args, **options):
        manager = TelegramBotManager()

        def _shutdown(signum, frame):
            self.stdout.write(
                self.style.WARNING(f"\nОтримано сигнал {signum}. Зупинка Telegram ботів..."),
            )
            manager.stop()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, _shutdown)
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, _shutdown)
        except (ValueError, AttributeError):
            # Not in main thread or signal not supported
            pass

        self.stdout.write(self.style.SUCCESS("Telegram Bot Poller запущено."))
        try:
            manager.run()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nЗупинка Telegram ботів..."))
            manager.stop()
        finally:
            self.stdout.write(self.style.SUCCESS("Telegram Bot Poller завершив роботу."))
