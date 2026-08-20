"""실제 MCP·LLM·Redis 없이 FastAPI→Graph 계약을 검증하는 통합 fake 조립기."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from app.agent.llm import FakeLLMPort
from app.cache.repository import MemoryCache
from app.core.dependencies import AppDependencies
from app.main import create_app
from app.mcp.client import FakeMCPPort, MCPClient
from tests.auth_helpers import authentication_dependencies


def tool_success(
    domain: str,
    data: list[dict[str, Any]],
    sources: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """실제 provider와 같은 success envelope fixture를 만든다."""
    return {
        "status": "success",
        "domain": domain,
        "message": None,
        "data": data,
        "sources": sources or [],
        "metadata": metadata or {},
    }


def database_success(domain: str, amount: int) -> dict[str, Any]:
    """DB provenance와 freshness metadata가 포함된 단일 행 envelope를 만든다."""
    return tool_success(
        domain,
        [{"category": domain, "amount": amount}],
        metadata={
            "generated_sql": "SELECT category, amount FROM reporting_view",
            "row_count": 1,
            "table_name": "reporting_view",
            "query_id": f"{domain}-query",
            "freshness_seconds": 30,
            "source_version": "fixture-v1",
        },
    )


def document_success() -> dict[str, Any]:
    """내부 file_path 없는 문서 data/source envelope를 만든다."""
    return tool_success(
        "document",
        [{"content": "휴가 규정은 승인 절차를 따릅니다.", "score": 0.9}],
        [{"document_id": "policy-001", "title": "휴가 규정", "page": 3}],
        {"index_version": "fixture-index-v1"},
    )


def build_fake_application(responses: dict[str, object]) -> tuple[FastAPI, FakeMCPPort, FakeLLMPort]:
    """호출 기록 가능한 fake provider와 독립 cache를 앱 factory에 주입한다."""
    port = FakeMCPPort(responses)
    llm = FakeLLMPort("fake answer")
    dependencies = AppDependencies(
        llm=llm,
        mcp=MCPClient(port),
        cache=MemoryCache(),
        configure_logging=lambda: None,
        **authentication_dependencies(),
    )
    return create_app(dependencies), port, llm
