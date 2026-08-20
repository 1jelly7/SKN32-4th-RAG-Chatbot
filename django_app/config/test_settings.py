"""외부 DB 없이 Django 계약 테스트를 실행하는 설정."""

from __future__ import annotations

import os

os.environ["DJANGO_DEBUG"] = "true"
os.environ["DJANGO_SECRET_KEY"] = "django-test-secret-key-that-is-at-least-32-bytes"
os.environ["AUTH_INTROSPECTION_KEY"] = "test-introspection-key-that-is-at-least-32-bytes"
os.environ["LEGACY_AUTH_ROLLBACK_WINDOW"] = "true"
os.environ["DJANGO_SERVE_STATIC_FILES"] = "true"

from django_app.config.settings import *  # noqa: F403,E402

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django_app.accounts.password_hashers.LegacyScryptPasswordHasher",
]
