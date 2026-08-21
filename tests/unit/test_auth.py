"""FastAPI의 Django 인증 gateway와 역할별 DB 정책 계약."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.gateway import AuthenticatedUser, AuthenticationUnavailableError
from app.auth.policy import allowed_databases
from app.cache.repository import MemoryCache
from app.core.dependencies import AppDependencies
from app.main import create_app
from tests.auth_helpers import FakeAuthenticationGateway


class _MarkerGraph:
    """사용자별 cache miss 여부를 검증하는 비동기 그래프 대역."""

    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, state: dict[str, object]) -> dict[str, object]:
        self.calls += 1
        user_context = state["user_context"]
        return {
            **state,
            "answer": f"private-{user_context['username']}",
            "sources": [],
            "tables": [],
            "route": "GENERAL",
        }


class _UnavailableGateway:
    async def authenticate(self, session_token: str) -> AuthenticatedUser | None:
        raise AuthenticationUnavailableError("unavailable")


def _client(gateway: object) -> TestClient:
    app = create_app(AppDependencies(cache=MemoryCache(), auth_gateway=gateway))
    return TestClient(app)


def _user(
    user_id: int,
    username: str,
    display_name: str,
    role: str,
    session_id: str,
) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id,
        username=username,
        display_name=display_name,
        role=role,
        session_id=session_id,
    )


def test_missing_or_unknown_django_session_is_unauthorized() -> None:
    gateway = FakeAuthenticationGateway({"known": _user(1, "known", "Known", "admin", "opaque-known")})
    with _client(gateway) as client:
        assert client.post("/api/chat", json={"question": "hello"}).status_code == 401
        client.cookies.set("chatbot_session", "unknown")
        response = client.post("/api/chat", json={"question": "hello"})
    assert response.status_code == 401


def test_authentication_service_failure_is_503() -> None:
    with _client(_UnavailableGateway()) as client:
        client.cookies.set("chatbot_session", "session")
        response = client.post("/api/chat", json={"question": "hello"})
    assert response.status_code == 503
    assert response.json()["detail"] == "인증 서비스를 사용할 수 없습니다."


def test_role_database_policy() -> None:
    assert allowed_databases("hr") == ["document_db"]
    assert allowed_databases("finance") == ["document_db", "purchase_db", "sales_db"]


def test_hr_database_question_is_rejected_before_query_execution() -> None:
    """HR 사용자는 Data MCP가 DB에 연결하기 전에 HTTP 403을 받는다."""
    gateway = FakeAuthenticationGateway(
        {"hr-session": _user(2, "hr", "HR", "hr", "opaque-hr-session")}
    )
    with _client(gateway) as client:
        client.cookies.set("chatbot_session", "hr-session")
        response = client.post("/api/chat", json={"question": "공급업체별 구매 지출"})

    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN"


def test_answer_cache_is_not_shared_between_authenticated_users() -> None:
    """동일 역할·질문이라도 다른 사용자의 private answer cache를 재사용하지 않는다."""
    gateway = FakeAuthenticationGateway(
        {
            "first": _user(1, "admin", "Admin", "admin", "opaque-first"),
            "second": _user(5, "admin-two", "Admin Two", "admin", "opaque-second"),
        }
    )
    graph = _MarkerGraph()
    app = create_app(AppDependencies(cache=MemoryCache(), auth_gateway=gateway))
    app.state.graph = graph

    with TestClient(app) as first_client, TestClient(app) as second_client:
        first_client.cookies.set("chatbot_session", "first")
        first = first_client.post("/api/chat", json={"question": "same-question"})
        second_client.cookies.set("chatbot_session", "second")
        second = second_client.post("/api/chat", json={"question": "same-question"})

    assert first.json()["cached"] is False
    assert second.json()["cached"] is False
    assert second.json()["answer"] == "private-admin-two"
    assert graph.calls == 2
