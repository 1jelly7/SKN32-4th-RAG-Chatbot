"""MCP 빈 결과·query error·malformed payload·timeout의 HTTP 매핑 계약."""

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
            "TIMEOUT",
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
    """오류 종류를 구분하되 provider 내부 메시지 없이 공개 상태로 변환한다."""
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


@pytest.mark.integration
def test_insufficient_evidence_retries_once_then_returns_422() -> None:
    """저품질 evidence를 정상 답변으로 가장하지 않고 제한된 보강 후 종료한다."""
    low_quality_document = {
        "status": "success",
        "domain": "document",
        "message": None,
        "data": [{"content": "낮은 관련성", "score": 0.1}],
        "sources": [{"document_id": "low-1", "title": "낮은 관련성 문서"}],
        "metadata": {},
    }
    application, port, llm = build_fake_application(
        {
            "search_documents": low_quality_document,
            "query_purchase": database_success("purchase", 100),
            "query_sales": database_success("sales", 200),
        }
    )

    with TestClient(application) as client:
        response = client.post("/api/chat", json={"question": "휴가 규정 알려줘"})

    assert response.status_code == 422
    assert response.json()["error_code"] == "EVIDENCE_INSUFFICIENT"
    assert [call.tool_name for call in port.calls] == ["search_documents", "search_documents"]
    assert llm.calls == []
