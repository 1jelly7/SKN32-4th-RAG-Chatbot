"""FastAPI DI, cache-first 순서, 안전한 Tool 오류 응답의 단위 계약."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent.llm import LLMClient
from app.cache.key import make_cache_key
from app.cache.repository import CacheValue, MemoryCache
from app.core.dependencies import AppDependencies
from app.main import create_app
from app.mcp.client import (
    MCPEvidenceInsufficientError,
    MCPClient,
    MCPInternalError,
    MCPInvalidInputError,
    MCPMalformedPayloadError,
    MCPNoResultError,
    MCPQueryError,
    MCPTimeoutError,
)
from tests.auth_helpers import TEST_ADMIN_CONTEXT, authentication_dependencies, login


class FakeLLMClient(LLMClient):
    """생성자에서 실제 OpenAI client를 만들지 않는 API 조립용 대역."""
    def __init__(self) -> None:
        pass


class FakeMCPClient(MCPClient):
    """생성자에서 실제 transport를 요구하지 않는 API 조립용 대역."""
    def __init__(self) -> None:
        pass


class RecordingCache(MemoryCache):
    """cache lookup/write 순서와 호출 횟수를 기록하는 저장소 대역."""
    def __init__(self) -> None:
        super().__init__()
        self.events: list[str] = []
        self.get_calls = 0
        self.set_calls = 0

    def get(self, key: str) -> CacheValue | None:
        self.get_calls += 1
        self.events.append("cache_get")
        return super().get(key)

    def set(self, key: str, value: CacheValue, ttl_seconds: int = 300) -> None:
        self.set_calls += 1
        self.events.append("cache_set")
        super().set(key, value, ttl_seconds)


class CountingGraph:
    """cache miss에서만 호출돼야 하는 downstream 작업 횟수를 기록한다."""
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events
        self.graph_calls = 0
        self.llm_calls = 0
        self.mcp_calls = 0

    async def ainvoke(self, state: dict[str, object]) -> dict[str, object]:
        self.graph_calls += 1
        if self.events is not None:
            self.events.append("graph")
        self.llm_calls += 1
        self.mcp_calls += 1
        return {
            **state,
            "answer": "cached answer",
            "sources": [],
            "tables": [],
            "route": "GENERAL",
        }


class ErrorGraph:
    """API 오류 매핑을 위해 지정된 경계 예외를 발생시킨다."""
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def ainvoke(self, state: dict[str, object]) -> dict[str, object]:
        raise self.error


def _application(cache: MemoryCache, graph: object):
    dependencies = AppDependencies(
        llm=FakeLLMClient(),
        mcp=FakeMCPClient(),
        cache=cache,
        configure_logging=lambda: None,
        **authentication_dependencies(),
    )
    application = create_app(dependencies)
    application.state.graph = graph
    application.state.cache_key_context = {
        "document_index_version": "documents-v2",
        "database_freshness_bucket": "fresh-2026-08-01",
        "prompt_version": "prompt-v2",
        "model_id": "model-v2",
    }
    return application


def test_health_uses_injected_dependencies_without_file_logging(tmp_path: Path) -> None:
    configured = False
    log_path = tmp_path / "app.log.txt"

    def configure_test_logging() -> None:
        nonlocal configured
        configured = True

    fake_llm = FakeLLMClient()
    fake_mcp = FakeMCPClient()
    fake_cache = MemoryCache()
    dependencies = AppDependencies(
        llm=fake_llm,
        mcp=fake_mcp,
        cache=fake_cache,
        configure_logging=configure_test_logging,
    )
    application = create_app(dependencies)

    with TestClient(application) as client:
        assert client.get("/api/health").status_code == 200

    assert configured is True
    assert application.state.dependencies is dependencies
    assert application.state.dependencies.llm is fake_llm
    assert application.state.dependencies.mcp is fake_mcp
    assert application.state.dependencies.cache is fake_cache
    assert log_path.exists() is False


def test_ui_entry_and_assets_disable_browser_cache() -> None:
    """개발 중 UI 변경이 이전 HTML·CSS·JS 캐시에 가려지지 않게 한다."""
    application = _application(MemoryCache(), CountingGraph())

    with TestClient(application) as client:
        for path in ("/", "/style.css", "/chat.js"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"


def test_cache_hit_skips_graph_llm_and_mcp_calls() -> None:
    cache = RecordingCache()
    graph = CountingGraph()
    application = _application(cache, graph)
    application.state.cache_key_context["user_context"] = TEST_ADMIN_CONTEXT
    state = {"question": "캐시 질문", **application.state.cache_key_context}
    cache.set(
        make_cache_key(state),
        {"answer": "stored", "sources": [], "tables": [], "route": "GENERAL"},
    )
    cache.get_calls = 0
    cache.set_calls = 0
    cache.events.clear()

    with TestClient(application) as client:
        login(client)
        response = client.post("/api/chat", json={"question": "캐시 질문"})

    assert response.status_code == 200
    assert response.json()["cached"] is True
    assert cache.get_calls == 1
    assert cache.set_calls == 0
    assert cache.events == ["cache_get"]
    assert graph.graph_calls == 0
    assert graph.llm_calls == 0
    assert graph.mcp_calls == 0


def test_cache_miss_invokes_graph_once_then_writes_and_hits() -> None:
    cache = RecordingCache()
    graph = CountingGraph(cache.events)
    application = _application(cache, graph)

    with TestClient(application) as client:
        login(client)
        first = client.post("/api/chat", json={"question": "새 질문"})
        second = client.post("/api/chat", json={"question": "새 질문"})

    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert cache.get_calls == 2
    assert cache.set_calls == 1
    assert cache.events == ["cache_get", "graph", "cache_set", "cache_get"]
    assert graph.graph_calls == 1
    assert graph.llm_calls == 1
    assert graph.mcp_calls == 1


def test_invalid_chat_request_does_not_invoke_cache_or_graph() -> None:
    cache = RecordingCache()
    graph = CountingGraph()
    application = _application(cache, graph)

    with TestClient(application) as client:
        login(client)
        response = client.post("/api/chat", json={"question": ""})

    assert response.status_code == 422
    assert cache.get_calls == 0
    assert cache.set_calls == 0
    assert graph.graph_calls == 0
    assert graph.llm_calls == 0
    assert graph.mcp_calls == 0


@pytest.mark.parametrize(
    ("error", "status_code", "error_code"),
    [
        (MCPNoResultError("query_purchase", "secret=hidden"), 404, "NO_RESULT"),
        (MCPInvalidInputError("query_purchase", "secret=hidden"), 400, "INVALID_INPUT"),
        (MCPEvidenceInsufficientError("query_purchase", "secret=hidden"), 422, "EVIDENCE_INSUFFICIENT"),
        (MCPQueryError("query_purchase", "password=hidden"), 502, "QUERY_ERROR"),
        (MCPInternalError("query_purchase", "secret=hidden"), 502, "INTERNAL_ERROR"),
        (MCPTimeoutError("query_purchase", "token=hidden"), 504, "TIMEOUT"),
        (MCPMalformedPayloadError("query_purchase", "key=hidden"), 502, "INTERNAL_ERROR"),
    ],
)
def test_tool_errors_use_safe_contract_response(
    error: Exception, status_code: int, error_code: str
) -> None:
    application = _application(MemoryCache(), ErrorGraph(error))

    with TestClient(application) as client:
        login(client)
        response = client.post("/api/chat", json={"question": "오류 질문"})

    assert response.status_code == status_code
    assert response.json()["error_code"] == error_code
    assert "hidden" not in response.text


def test_session_id_is_hashed_into_cache_context() -> None:
    """같은 질문이라도 다른 세션의 답변을 공유하지 않게 한다."""
    cache = RecordingCache()
    graph = CountingGraph()
    application = _application(cache, graph)

    with TestClient(application) as client:
        login(client)
        first = client.post("/api/chat", json={"question": "세션 질문", "session_id": "session-a"})
        second = client.post("/api/chat", json={"question": "세션 질문", "session_id": "session-b"})
        repeat = client.post("/api/chat", json={"question": "세션 질문", "session_id": "session-a"})

    assert first.json()["cached"] is False
    assert second.json()["cached"] is False
    assert repeat.json()["cached"] is True
    assert graph.graph_calls == 2
