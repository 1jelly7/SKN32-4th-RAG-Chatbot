"""보호 API 계약 테스트에서 Django 인증 확인을 대체하는 공통 도우미."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.gateway import AuthenticatedUser

TEST_USERNAME = "test-admin"
TEST_PASSWORD = "test-password"
TEST_SESSION_TOKEN = "test-django-session"
TEST_ADMIN_CONTEXT: dict[str, object] = {
    "user_id": 1,
    "username": TEST_USERNAME,
    "display_name": "Test Admin",
    "role": "admin",
    "allowed_databases": ["document_db", "purchase_db", "sales_db"],
}


class FakeAuthenticationGateway:
    """세션 토큰별 사용자 컨텍스트를 반환하는 비네트워크 인증 대역."""

    def __init__(self, sessions: dict[str, AuthenticatedUser] | None = None) -> None:
        self.sessions = sessions or {
            TEST_SESSION_TOKEN: AuthenticatedUser(
                user_id=1,
                username=TEST_USERNAME,
                display_name="Test Admin",
                role="admin",
                session_id="opaque-test-session",
            )
        }

    async def authenticate(self, session_token: str) -> AuthenticatedUser | None:
        return self.sessions.get(session_token)


def authentication_dependencies() -> dict[str, object]:
    """테스트 앱에 외부 호출 없는 인증 gateway를 제공한다."""
    return {"auth_gateway": FakeAuthenticationGateway()}


def login(client: TestClient, session_token: str = TEST_SESSION_TOKEN) -> None:
    """Django에서 발급됐다고 가정한 세션 쿠키를 테스트 client에 설정한다."""
    client.cookies.set("chatbot_session", session_token)
