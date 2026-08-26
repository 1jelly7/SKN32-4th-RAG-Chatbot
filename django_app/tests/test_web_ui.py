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
    policy = response.headers["Content-Security-Policy"]
    assert "script-src 'self'" in policy
    assert "script-src 'unsafe-inline'" not in policy
    assert "connect-src 'self'" in policy
    assert "object-src 'none'" in policy
    assert "frame-ancestors 'none'" in policy


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


def test_ui_script_renders_tables_charts_and_failure_states_without_unsafe_html() -> (
    None
):
    """표·차트·문서 다운로드·인증 및 부분 실패 UI 계약을 유지한다."""
    script = finders.find("web/chat.js")
    assert script is not None
    source = Path(script).read_text(encoding="utf-8")

    assert "function mountTableBlock(container, table, blockId)" in source
    assert '<table class="data-table">' in source
    assert "chartInstance = new Chart(canvas" in source
    assert "maintainAspectRatio: false" in source
    assert "function handleDownload(button)" in source
    assert "response.status === 401" in source
    assert (
        "showLogin(); throw new Error('세션이 만료되었습니다. 다시 로그인하세요.');"
        in source
    )
    assert "function evidenceStatusNote(status)" in source
    assert "PARTIALLY_SUPPORTED: '일부 조회 결과를 확인할 수 없어" in source
    assert "INSUFFICIENT: '답변에 필요한 근거가 부족합니다." in source
    assert "error instanceof TypeError" in source
    assert "escapeHtml(table.sql)" in source
    assert "escapeHtml(chunk.text)" in source
    assert "textContent = message" in source


def test_ui_template_loads_only_same_origin_script_assets() -> None:
    """CSP와 일치하게 template은 외부 script·stylesheet URL을 추가하지 않는다."""
    template = Path("django_app/web/templates/web/index.html").read_text(
        encoding="utf-8"
    )

    assert "https://" not in template
    assert "http://" not in template
    assert (
        "<script src=\"{% static 'web/vendor/chart.umd.min.js' %}\"></script>"
        in template
    )
    auth_script = "<script src=\"{% static 'web/auth.js' %}\"></script>"
    chat_script = "<script src=\"{% static 'web/chat.js' %}\"></script>"
    assert auth_script in template
    assert "<script src=\"{% static 'web/chat.js' %}\"></script>" in template
    assert template.index(auth_script) < template.index(chat_script)


def test_local_gateway_sets_immutable_cache_only_for_static_assets() -> None:
    """HTML의 no-cache 응답과 hash된 정적 자산의 장기 cache를 분리한다."""
    config = Path("deploy/nginx/local.conf").read_text(encoding="utf-8")

    assert (
        'add_header Cache-Control "public, max-age=31536000, immutable" always;'
        in config
    )
