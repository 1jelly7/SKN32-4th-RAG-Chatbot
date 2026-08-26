"""로그인 UI가 비동기 세션 복원 결과에 의해 되돌아가지 않는지 검증한다."""

from pathlib import Path


WEB_ROOT = Path("django_app/web")
WEB_SCRIPT = WEB_ROOT / "static/web/chat.js"
WEB_AUTH_SCRIPT = WEB_ROOT / "static/web/auth.js"
WEB_STYLE = WEB_ROOT / "static/web/style.css"
WEB_TEMPLATE = WEB_ROOT / "templates/web/index.html"


def test_login_invalidates_stale_session_restore_result() -> None:
    """초기 /auth/me 401이 로그인 성공 후 화면을 덮어쓰지 않게 한다."""
    script = WEB_AUTH_SCRIPT.read_text(encoding="utf-8")
    assert "let auth_state_revision = 0;" in script
    assert (
        "loginForm.addEventListener('submit', () => { auth_state_revision += 1; }, true);"
        in script
    )
    assert "if (revision !== auth_state_revision) return;" in script


def test_hidden_login_screen_is_not_overridden_by_grid_layout() -> None:
    """hidden 속성이 로그인 오버레이를 실제로 화면에서 제거해야 한다."""
    stylesheet = WEB_STYLE.read_text(encoding="utf-8")
    assert ".login-screen[hidden] { display: none; }" in stylesheet


def test_logout_clears_messages_and_aborts_pending_chat() -> None:
    """이전 사용자의 DOM과 늦게 도착한 응답이 다음 로그인에 남지 않아야 한다."""
    script = WEB_SCRIPT.read_text(encoding="utf-8")
    assert "function clearApplicationState()" in script
    assert "messages.replaceChildren();" in script
    assert "activeRequestController?.abort();" in script
    assert "signal: activeRequestController.signal" in script


def test_login_and_logout_send_django_csrf_token() -> None:
    """세션 쿠키 기반 쓰기 요청은 Django CSRF 검증을 우회하지 않아야 한다."""
    script = WEB_AUTH_SCRIPT.read_text(encoding="utf-8")
    assert "fetch('/api/auth/csrf')" in script
    assert "'X-CSRFToken': csrfTokenValue" in script
    assert "headers: await csrfHeaders()" in script


def test_chart_ui_uses_local_bundle_and_stable_sizing() -> None:
    index = WEB_TEMPLATE.read_text(encoding="utf-8")
    script = WEB_SCRIPT.read_text(encoding="utf-8")
    stylesheet = WEB_STYLE.read_text(encoding="utf-8")

    assert "{% static 'web/vendor/chart.umd.min.js' %}" in index
    assert "cdnjs.cloudflare.com" not in index
    assert "const chartType = table.chart_type || 'bar';" in script
    assert "maintainAspectRatio: false" in script
    assert "toLocaleString()" in script
    assert "isCurrencyColumn" in script
    assert ".chart-wrap { height: 320px;" in stylesheet


def test_document_download_uses_server_filename_before_title_fallback() -> None:
    """Blob URL 다운로드도 Content-Disposition의 확장자를 보존해야 한다."""
    script = WEB_SCRIPT.read_text(encoding="utf-8")

    assert "function downloadFileName(response, fallbackFileName)" in script
    assert "filename\\*\\s*=\\s*UTF-8''" in script
    assert "link.download = downloadFileName(response, fileName);" in script


def test_chat_does_not_parse_gateway_html_as_json() -> None:
    """게이트웨이 HTML 오류 페이지가 JSON 파싱 예외로 노출되지 않아야 한다."""
    script = WEB_SCRIPT.read_text(encoding="utf-8")

    assert "async function chatResponsePayload(response)" in script
    assert "response.headers.get('content-type')" in script
    assert "const data = await chatResponsePayload(response);" in script
