"""로그인 UI가 비동기 세션 복원 결과에 의해 되돌아가지 않는지 검증한다."""

from pathlib import Path


WEB_SCRIPT = Path("app/web/chat.js")
WEB_STYLE = Path("app/web/style.css")


def test_login_invalidates_stale_session_restore_result() -> None:
    """초기 /auth/me 401이 로그인 성공 후 화면을 덮어쓰지 않게 한다."""
    script = WEB_SCRIPT.read_text(encoding="utf-8")
    assert "let auth_state_revision = 0;" in script
    assert "loginForm.addEventListener('submit', () => { auth_state_revision += 1; }, true);" in script
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


def test_chart_ui_uses_local_bundle_and_stable_sizing() -> None:
    index = Path("app/web/index.html").read_text(encoding="utf-8")
    script = WEB_SCRIPT.read_text(encoding="utf-8")
    stylesheet = WEB_STYLE.read_text(encoding="utf-8")

    assert "/static/vendor/chart.umd.min.js" in index
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
