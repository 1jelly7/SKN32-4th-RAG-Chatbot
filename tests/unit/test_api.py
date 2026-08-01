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
    MCPClient,
    MCPMalformedPayloadError,
    MCPNoResultError,
    MCPQueryError,
    MCPTimeoutError,
)


class FakeLLMClient(LLMClient):
    def __init__(self) -> None:
        pass


class FakeMCPClient(MCPClient):
    def __init__(self) -> None:
        pass


class RecordingCache(MemoryCache):
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


def test_cache_hit_skips_graph_llm_and_mcp_calls() -> None:
    cache = RecordingCache()
    graph = CountingGraph()
    application = _application(cache, graph)
    state = {"question": "캐시 질문", **application.state.cache_key_context}
    cache.set(
        make_cache_key(state),
        {"answer": "stored", "sources": [], "tables": [], "route": "GENERAL"},
    )
    cache.get_calls = 0
    cache.set_calls = 0
    cache.events.clear()

    with TestClient(application) as client:
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
        (MCPQueryError("query_purchase", "password=hidden"), 502, "QUERY_ERROR"),
        (MCPTimeoutError("query_purchase", "token=hidden"), 504, "QUERY_ERROR"),
        (MCPMalformedPayloadError("query_purchase", "key=hidden"), 502, "INTERNAL_ERROR"),
    ],
)
def test_tool_errors_use_safe_contract_response(
    error: Exception, status_code: int, error_code: str
) -> None:
    application = _application(MemoryCache(), ErrorGraph(error))

    with TestClient(application) as client:
        response = client.post("/api/chat", json={"question": "오류 질문"})

    assert response.status_code == status_code
    assert response.json()["error_code"] == error_code
    assert "hidden" not in response.text
