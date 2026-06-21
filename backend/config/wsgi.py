"""WSGI config for ZROZUMILOAI project."""
import os

worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gevent')
if worker_class == 'gevent':
    from psycogreen.gevent import patch_psycopg
    patch_psycopg()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
