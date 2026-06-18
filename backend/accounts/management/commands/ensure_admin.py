"""Create superuser from .env when no admin exists in the database."""
import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = (
        'Перевіряє наявність адміністратора в БД і створює суперкористувача '
        'з DJANGO_ADMIN_* змінних середовища (.env), якщо його немає.'
    )

    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.SUCCESS('Адміністратор уже існує — пропуск.'),
            )
            return

        username = os.getenv('DJANGO_ADMIN_USERNAME', 'admin')
        password = os.getenv('DJANGO_ADMIN_PASSWORD', '')
        email = os.getenv('DJANGO_ADMIN_EMAIL', f'{username}@localhost')

        if not password:
            self.stdout.write(
                self.style.WARNING(
                    'DJANGO_ADMIN_PASSWORD не задано — '
                    'суперкористувач не створений.',
                ),
            )
            return

        os.environ['DJANGO_SUPERUSER_USERNAME'] = username
        os.environ['DJANGO_SUPERUSER_PASSWORD'] = password
        os.environ['DJANGO_SUPERUSER_EMAIL'] = email

        call_command('createsuperuser', '--noinput')

        from accounts.services import ensure_api_key

        user = User.objects.get(username=username)
        raw_key = ensure_api_key(user)
        if raw_key:
            self.stdout.write(f'API ключ: {raw_key}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Суперкористувача "{username}" створено.',
            ),
        )
