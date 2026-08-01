from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from tests.integration.chat_fakes import build_fake_application, database_success, document_success


@pytest.mark.integration
@pytest.mark.parametrize(
    ("question", "response", "expected_status", "expected_code", "expected_tool"),
    [
        (
            "휴가 규정 알려줘",
            {"status": "success", "domain": "document", "message": None, "data": [], "sources": [], "metadata": {}},
            404,
            "NO_RESULT",
            "search_documents",
        ),
        (
            "고객별 매출 알려줘",
            {"status": "error", "domain": "sales", "message": "query failed", "error_code": "QUERY_ERROR"},
            502,
            "QUERY_ERROR",
            "query_sales",
        ),
        (
            "고객별 매출 알려줘",
            {"status": "success"},
            502,
            "INTERNAL_ERROR",
            "query_sales",
        ),
        (
            "고객별 매출 알려줘",
            asyncio.TimeoutError(),
            504,
            "QUERY_ERROR",
            "query_sales",
        ),
    ],
)
def test_graph_mcp_errors_use_http_contract(
    question: str,
    response: object,
    expected_status: int,
    expected_code: str,
    expected_tool: str,
) -> None:
    responses: dict[str, object] = {
        "search_documents": document_success(),
        "query_purchase": database_success("purchase", 100),
        "query_sales": database_success("sales", 200),
    }
    responses[expected_tool] = response
    application, port, llm = build_fake_application(responses)

    with TestClient(application) as client:
        result = client.post("/api/chat", json={"question": question})

    assert result.status_code == expected_status
    assert result.json()["error_code"] == expected_code
    assert [call.tool_name for call in port.calls] == [expected_tool]
    assert llm.calls == []
