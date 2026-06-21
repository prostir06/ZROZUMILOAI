"""Django settings for ZROZUMILOAI personal assistant panel."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv(
    'DJANGO_SECRET_KEY',
    'django-insecure-change-me-in-production',
)

DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.getenv(
    'DJANGO_ALLOWED_HOSTS',
    'localhost,127.0.0.1,backend',
).split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'accounts',
    'chats',
    'workspaces',
    'ollama_proxy',
    'backups',
]

_use_sqlite = os.getenv('USE_SQLITE', '').lower() in ('true', '1', 'yes')
if not _use_sqlite:
    INSTALLED_APPS.append('pgvector.django')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'zrozumiloai'),
        'USER': os.getenv('POSTGRES_USER', 'zrozumiloai'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'zrozumiloai'),
        'HOST': os.getenv('POSTGRES_HOST', 'db'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}

if os.getenv('USE_SQLITE', '').lower() in ('true', '1', 'yes'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'UserAttributeSimilarityValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'MinimumLengthValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'CommonPasswordValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'NumericPasswordValidator'
        ),
    },
]

LANGUAGE_CODE = 'uk'
TIME_ZONE = 'Europe/Kyiv'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'accounts.authentication.ApiKeyAuthentication',
        'workspaces.widget_auth.WidgetTokenAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': None,
    'DEFAULT_THROTTLE_RATES': {
        'auth_login': os.getenv('AUTH_LOGIN_RATE', '10/minute'),
        'auth_register': os.getenv('AUTH_REGISTER_RATE', '5/minute'),
        'widget_chat': os.getenv('WIDGET_CHAT_RATE', '60/minute'),
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=12),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
}

CORS_ALLOWED_ORIGINS = os.getenv(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://localhost:3000,http://localhost',
).split(',')

# Sandbox iframe (без allow-same-origin) надсилає Origin: null — потрібно для embed API.
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^null$',
]

CORS_ALLOW_CREDENTIALS = True

ALLOW_REGISTRATION = os.getenv(
    'ALLOW_REGISTRATION',
    'True',
).lower() in ('true', '1', 'yes')

OLLAMA_BASE_URL = os.getenv(
    'OLLAMA_BASE_URL',
    'http://localhost:11434',
)

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

RAG_ENABLED = os.getenv('RAG_ENABLED', 'True').lower() in ('true', '1', 'yes')
RAG_EMBED_MODEL = os.getenv('RAG_EMBED_MODEL', 'nomic-embed-text')
RAG_EMBED_DIMENSIONS = int(os.getenv('RAG_EMBED_DIMENSIONS', '768'))
RAG_CHUNK_SIZE = int(os.getenv('RAG_CHUNK_SIZE', '800'))
RAG_CHUNK_OVERLAP = int(os.getenv('RAG_CHUNK_OVERLAP', '100'))
RAG_TOP_K = int(os.getenv('RAG_TOP_K', '4'))
RAG_MAX_FILE_SIZE = int(os.getenv('RAG_MAX_FILE_SIZE', str(10 * 1024 * 1024)))

_backup_dir = os.getenv('BACKUP_DIR', str(BASE_DIR.parent / 'backup'))
BACKUP_DIR = Path(_backup_dir)
if not BACKUP_DIR.is_absolute():
    BACKUP_DIR = (BASE_DIR.parent / BACKUP_DIR).resolve()

_cache_dir = Path(os.getenv('DJANGO_CACHE_DIR', str(BASE_DIR / 'cache')))
_cache_dir.mkdir(parents=True, exist_ok=True)

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': str(_cache_dir),
    },
}
