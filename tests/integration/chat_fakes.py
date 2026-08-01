from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from app.agent.llm import FakeLLMPort
from app.cache.repository import MemoryCache
from app.core.dependencies import AppDependencies
from app.main import create_app
from app.mcp.client import FakeMCPPort, MCPClient


def tool_success(
    domain: str,
    data: list[dict[str, Any]],
    sources: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "success",
        "domain": domain,
        "message": None,
        "data": data,
        "sources": sources or [],
        "metadata": metadata or {},
    }


def database_success(domain: str, amount: int) -> dict[str, Any]:
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
    return tool_success(
        "document",
        [{"content": "휴가 규정은 승인 절차를 따릅니다.", "score": 0.9}],
        [{"document_id": "policy-001", "title": "휴가 규정", "page": 3}],
        {"index_version": "fixture-index-v1"},
    )


def build_fake_application(responses: dict[str, object]) -> tuple[FastAPI, FakeMCPPort, FakeLLMPort]:
    port = FakeMCPPort(responses)
    llm = FakeLLMPort("fake answer")
    dependencies = AppDependencies(
        llm=llm,
        mcp=MCPClient(port),
        cache=MemoryCache(),
        configure_logging=lambda: None,
    )
    return create_app(dependencies), port, llm
