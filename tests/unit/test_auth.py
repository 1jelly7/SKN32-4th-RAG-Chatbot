"""서명 세션, 로그인, 보호 API, 역할별 DB 정책의 단위 계약이다."""

from fastapi.testclient import TestClient

from app.auth.models import Account
from app.auth.passwords import hash_password, verify_password
from app.auth.policy import allowed_databases
from app.auth.repository import MemoryAccountRepository
from app.auth.service import AuthenticationService
from app.cache.repository import MemoryCache
from app.core.dependencies import AppDependencies
from app.main import create_app


class _MarkerGraph:
    """사용자별 cache miss 여부를 검증하는 비동기 그래프 대역."""

    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, state: dict[str, object]) -> dict[str, object]:
        self.calls += 1
        return {**state, "answer": f"private-{state['user_context']['username']}", "sources": [], "tables": [], "route": "GENERAL"}


def _client() -> TestClient:
    repository = MemoryAccountRepository([
        Account(1, "admin", hash_password("admin-password"), "Admin", "admin", True),
        Account(2, "hr", hash_password("hr-password"), "HR", "hr", True),
        Account(3, "finance", hash_password("finance-password"), "Finance", "finance", True),
        Account(4, "disabled", hash_password("disabled-password"), "Disabled", "hr", False),
    ])
    app = create_app(AppDependencies(cache=MemoryCache(), auth_service=AuthenticationService(repository), auth_secret="test-secret-that-is-long-enough-for-signing"))
    return TestClient(app)


def test_password_hash_never_contains_plaintext_and_verifies() -> None:
    encoded = hash_password("correct horse battery staple")
    assert "correct horse" not in encoded
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong", encoded)


def test_login_me_logout_and_protected_chat() -> None:
    with _client() as client:
        assert client.post("/api/chat", json={"question": "hello"}).status_code == 401
        bad = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert bad.status_code == 401
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin-password"})
        assert login.status_code == 200
        assert "password_hash" not in login.text
        assert login.cookies.get("chatbot_session")
        assert client.get("/api/auth/me").json()["allowed_databases"] == allowed_databases("admin")
        previous_token = login.cookies.get("chatbot_session")
        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401
        assert client.get("/api/auth/me", cookies={"chatbot_session": previous_token}).status_code == 401


def test_inactive_account_cannot_log_in() -> None:
    with _client() as client:
        assert client.post("/api/auth/login", json={"username": "disabled", "password": "disabled-password"}).status_code == 401


def test_role_database_policy() -> None:
    assert allowed_databases("hr") == ["account_db", "document_db"]
    assert allowed_databases("finance") == ["document_db", "purchase_db", "sales_db"]


def test_hr_database_question_is_rejected_before_query_execution() -> None:
    """HR 사용자는 Data MCP가 DB에 연결하기 전에 HTTP 403을 받는다."""
    with _client() as client:
        assert client.post(
            "/api/auth/login",
            json={"username": "hr", "password": "hr-password"},
        ).status_code == 200
        response = client.post("/api/chat", json={"question": "공급업체별 구매 지출"})

    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN"


def test_answer_cache_is_not_shared_between_authenticated_users() -> None:
    """동일 역할·질문이라도 다른 사용자의 private answer cache를 재사용하지 않는다."""
    repository = MemoryAccountRepository([
        Account(1, "admin", hash_password("admin-password"), "Admin", "admin", True),
        Account(5, "admin-two", hash_password("admin-two-password"), "Admin Two", "admin", True),
    ])
    graph = _MarkerGraph()
    app = create_app(AppDependencies(cache=MemoryCache(), auth_service=AuthenticationService(repository), auth_secret="test-secret-that-is-long-enough-for-signing"))
    app.state.graph = graph

    with TestClient(app) as first_client, TestClient(app) as second_client:
        assert first_client.post("/api/auth/login", json={"username": "admin", "password": "admin-password"}).status_code == 200
        first = first_client.post("/api/chat", json={"question": "same-question"})
        assert second_client.post("/api/auth/login", json={"username": "admin-two", "password": "admin-two-password"}).status_code == 200
        second = second_client.post("/api/chat", json={"question": "same-question"})

    assert first.json()["cached"] is False
    assert second.json()["cached"] is False
    assert second.json()["answer"] == "private-admin-two"
    assert graph.calls == 2
