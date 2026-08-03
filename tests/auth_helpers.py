"""보호 API 계약 테스트에서 실제 로그인 쿠키를 발급하는 공통 도우미다."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.models import Account
from app.auth.passwords import hash_password
from app.auth.repository import MemoryAccountRepository
from app.auth.service import AuthenticationService
from app.core.dependencies import AppDependencies

TEST_USERNAME = "test-admin"
TEST_PASSWORD = "test-password"
TEST_AUTH_SECRET = "test-secret-that-is-long-enough-for-session-signing"
TEST_ADMIN_CONTEXT: dict[str, object] = {
    "user_id": 1,
    "username": TEST_USERNAME,
    "display_name": "Test Admin",
    "role": "admin",
    "allowed_databases": ["account_db", "document_db", "purchase_db", "sales_db"],
}


def authentication_dependencies() -> dict[str, object]:
    """테스트 앱에 실제 해시 검증을 수행하는 메모리 계정 저장소를 제공한다."""
    repository = MemoryAccountRepository([
        Account(1, TEST_USERNAME, hash_password(TEST_PASSWORD), "Test Admin", "admin", True),
    ])
    return {
        "auth_service": AuthenticationService(repository),
        "auth_secret": TEST_AUTH_SECRET,
        "auth_expire_minutes": 60,
        "auth_cookie_secure": False,
    }


def login(client: TestClient) -> None:
    """실제 로그인 API를 호출해 이후 보호 API 요청에 HttpOnly 쿠키를 유지한다."""
    response = client.post("/api/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert response.status_code == 200
