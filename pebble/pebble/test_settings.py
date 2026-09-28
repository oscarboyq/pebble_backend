"""Isolated in-memory SQLite test settings; no local database access needed.

Usage: ``python manage.py test --settings=pebble.test_settings``
"""
import os
import tempfile

os.environ.setdefault('DJANGO_SECRET_KEY', 'isolated-test-key-not-for-deployment')
os.environ.setdefault('DB_NAME', 'unused-in-tests')
os.environ.setdefault('DB_USER', 'unused-in-tests')
os.environ.setdefault('DB_PASSWORD', 'unused-in-tests')

from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

_test_media_directory = tempfile.TemporaryDirectory(prefix='pebble-test-media-')
MEDIA_ROOT = _test_media_directory.name
