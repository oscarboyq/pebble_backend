"""Small local environment loader with no third-party dependency."""

import json
import os

from django.core.exceptions import ImproperlyConfigured


def read_local_env(path):
    """Load KEY=VALUE lines; process environment always takes precedence.

    Quoted values use JSON string syntax so secrets can contain whitespace or
    shell metacharacters without being evaluated.
    """
    if not path.exists():
        return
    for number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise ImproperlyConfigured(f'Invalid environment line {number} in {path}')
        name, value = line.split('=', 1)
        name = name.strip()
        if not name.isidentifier():
            raise ImproperlyConfigured(f'Invalid environment key on line {number} in {path}')
        value = value.strip()
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ImproperlyConfigured(f'Invalid quoted value on line {number} in {path}') from exc
        os.environ.setdefault(name, value)


def env_required(name):
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f'{name} is required; set it in the environment or .env.local')
    return value


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    if value.lower() in ('1', 'true', 'yes', 'on'):
        return True
    if value.lower() in ('0', 'false', 'no', 'off'):
        return False
    raise ImproperlyConfigured(f'{name} must be true or false')


def env_list(name, default):
    value = os.environ.get(name)
    return [part.strip() for part in value.split(',') if part.strip()] if value is not None else default
