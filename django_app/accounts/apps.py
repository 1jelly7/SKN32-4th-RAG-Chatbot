"""accounts 애플리케이션 설정."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Django 인증·계정 경계의 앱 메타데이터."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "django_app.accounts"
    label = "accounts"
