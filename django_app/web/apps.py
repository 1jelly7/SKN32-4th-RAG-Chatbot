"""사용자 웹 애플리케이션 설정."""

from django.apps import AppConfig


class WebConfig(AppConfig):
    """계정 도메인과 분리된 사용자 화면 경계다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "django_app.web"
    label = "web"
