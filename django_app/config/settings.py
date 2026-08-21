"""Django 인증 서비스의 환경 변수 기반 실행 설정."""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")


def _boolean(name: str, default: bool = False) -> bool:
    """일반적인 환경 변수 불리언 표기를 엄격하게 읽는다."""
    value = os.getenv(name, str(default)).strip().lower()
    if value not in {"true", "false", "1", "0", "yes", "no"}:
        raise ImproperlyConfigured(f"{name} must be a boolean value")
    return value in {"true", "1", "yes"}


def _csv(name: str, default: str = "") -> list[str]:
    """쉼표 구분 환경 변수를 빈 항목 없이 반환한다."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _positive_int(name: str, default: int) -> int:
    """시간·포트 설정을 0보다 큰 정수로 제한한다."""
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be a positive integer") from None
    if value < 1:
        raise ImproperlyConfigured(f"{name} must be a positive integer")
    return value


DEBUG = _boolean("DJANGO_DEBUG")
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if len(SECRET_KEY) < 32 and not DEBUG:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must contain at least 32 characters when DJANGO_DEBUG is false"
    )
if not SECRET_KEY:
    SECRET_KEY = "development-only-django-secret-key"

ALLOWED_HOSTS = _csv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = _csv("DJANGO_CSRF_TRUSTED_ORIGINS")
SERVE_STATIC_FILES = _boolean("DJANGO_SERVE_STATIC_FILES")
AUTH_INTROSPECTION_KEY = os.getenv("AUTH_INTROSPECTION_KEY", "")
if len(AUTH_INTROSPECTION_KEY) < 32 and not DEBUG:
    raise ImproperlyConfigured(
        "AUTH_INTROSPECTION_KEY must contain at least 32 characters when DJANGO_DEBUG is false"
    )
LEGACY_ACCOUNT_TIME_ZONE = os.getenv("LEGACY_ACCOUNT_TIME_ZONE", "Asia/Seoul")
LEGACY_AUTH_ROLLBACK_WINDOW = _boolean("LEGACY_AUTH_ROLLBACK_WINDOW", True)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_app.accounts.apps.AccountsConfig",
    "django_app.web.apps.WebConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django_app.web.middleware.ContentSecurityPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "django_app.config.urls"
ASGI_APPLICATION = "django_app.config.asgi.application"
WSGI_APPLICATION = "django_app.config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "HOST": os.getenv("ACCOUNT_DB_HOST", "127.0.0.1"),
        "PORT": _positive_int("ACCOUNT_DB_PORT", 3306),
        "NAME": os.getenv("ACCOUNT_DB_NAME", "account_db"),
        "USER": os.getenv("ACCOUNT_DB_USER", ""),
        "PASSWORD": os.getenv("ACCOUNT_DB_PASSWORD", ""),
        "OPTIONS": {"charset": "utf8mb4"},
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django_app.accounts.password_hashers.LegacyScryptPasswordHasher",
]

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/django-static/"
STATIC_ROOT = PROJECT_ROOT / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_NAME = "chatbot_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = _boolean("AUTH_COOKIE_SECURE")
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = _positive_int("AUTH_SESSION_EXPIRE_SECONDS", 3600)
SESSION_SAVE_EVERY_REQUEST = False
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "django_app.accounts.views.csrf_failure"

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if _boolean("DJANGO_TRUST_X_FORWARDED_PROTO"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
