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
