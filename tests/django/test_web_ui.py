"""Django 사용자 UI와 정적 자산 계약."""

from __future__ import annotations

from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import Client
from django.urls import reverse

from django_app.config import settings as application_settings


def test_django_serves_chat_ui_shell_without_cache() -> None:
    """공개 루트는 Django template으로 렌더링되고 개발 중 HTML cache를 남기지 않는다."""
    response = Client().get(reverse("web:index"))

    assert response.status_code == 200
    assert response.templates[0].name == "web/index.html"
    assert "text/html" in response.headers["Content-Type"]
    assert "no-cache" in response.headers["Cache-Control"]
    assert "/django-static/web/style.css" in response.content.decode()
    assert "/django-static/web/chat.js" in response.content.decode()
    assert "/django-static/web/vendor/chart.umd.min.js" in response.content.decode()
    assert response.headers["Content-Security-Policy"] == (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    )


def test_django_admin_is_not_covered_by_web_ui_csp() -> None:
    """UI 전용 CSP가 Django Admin의 별도 자산 계약을 변경하지 않는다."""
    response = Client().get("/admin/")

    assert "Content-Security-Policy" not in response.headers


def test_django_staticfiles_discovers_all_ui_assets() -> None:
    """collectstatic가 Django web 앱이 소유하는 UI 자산을 모두 찾는다."""
    assert finders.find("web/style.css") is not None
    assert finders.find("web/chat.js") is not None
    assert finders.find("web/vendor/chart.umd.min.js") is not None
    assert application_settings.STORAGES["staticfiles"]["BACKEND"] == (
        "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    )


def test_development_static_routes_serve_ui_assets() -> None:
    """명시적 로컬 설정에서는 ASGI·WSGI 서버가 UI 자산을 직접 제공한다."""
    client = Client()

    stylesheet = client.get("/django-static/web/style.css")
    script = client.get("/django-static/web/chat.js")
    chart = client.get("/django-static/web/vendor/chart.umd.min.js")

    assert stylesheet.status_code == 200
    assert stylesheet.headers["Content-Type"].startswith("text/css")
    assert script.status_code == 200
    assert "javascript" in script.headers["Content-Type"]
    assert chart.status_code == 200
    assert "javascript" in chart.headers["Content-Type"]


def test_ui_script_restricts_untrusted_urls_to_known_safe_destinations() -> None:
    """출처 link와 다운로드 요청은 허용된 URL scheme·same-origin 경계만 사용한다."""
    script = finders.find("web/chat.js")
    assert script is not None
    source = Path(script).read_text(encoding="utf-8")

    assert "function safeWebUrl(value)" in source
    assert "['http:', 'https:'].includes(url.protocol)" in source
    assert "function safeDownloadUrl(value)" in source
    assert "url.origin !== window.location.origin" in source
    assert "url.pathname !== '/api/documents/download'" in source
    assert 'href="${escapeHtml(source.url)}"' not in source


def test_local_gateway_sets_immutable_cache_only_for_static_assets() -> None:
    """HTML의 no-cache 응답과 hash된 정적 자산의 장기 cache를 분리한다."""
    config = Path("deploy/nginx/local.conf").read_text(encoding="utf-8")

    assert 'add_header Cache-Control "public, max-age=31536000, immutable" always;' in config
