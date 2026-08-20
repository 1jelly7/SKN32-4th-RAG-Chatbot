"""Django 사용자 UI와 정적 자산 계약."""

from __future__ import annotations

from django.contrib.staticfiles import finders
from django.test import Client
from django.urls import reverse


def test_django_serves_chat_ui_shell_without_cache() -> None:
    """공개 루트는 Django template으로 렌더링되고 개발 중 HTML cache를 남기지 않는다."""
    response = Client().get(reverse("web:index"))

    assert response.status_code == 200
    assert response.templates[0].name == "web/index.html"
    assert "text/html" in response.headers["Content-Type"]
    assert "no-cache" in response.headers["Cache-Control"]
    assert "/django-static/web/style.css" in response.content.decode()
    assert "/django-static/web/chat.js" in response.content.decode()
    assert "/django-static/vendor/chart.umd.min.js" in response.content.decode()


def test_django_staticfiles_discovers_all_ui_assets() -> None:
    """collectstatic가 자체 UI source와 전환 기간 vendor bundle을 모두 찾는다."""
    assert finders.find("web/style.css") is not None
    assert finders.find("web/chat.js") is not None
    assert finders.find("vendor/chart.umd.min.js") is not None


def test_development_static_routes_serve_ui_assets() -> None:
    """명시적 로컬 설정에서는 ASGI·WSGI 서버가 UI 자산을 직접 제공한다."""
    client = Client()

    stylesheet = client.get("/django-static/web/style.css")
    script = client.get("/django-static/web/chat.js")
    chart = client.get("/django-static/vendor/chart.umd.min.js")

    assert stylesheet.status_code == 200
    assert stylesheet.headers["Content-Type"].startswith("text/css")
    assert script.status_code == 200
    assert "javascript" in script.headers["Content-Type"]
    assert chart.status_code == 200
    assert "javascript" in chart.headers["Content-Type"]
