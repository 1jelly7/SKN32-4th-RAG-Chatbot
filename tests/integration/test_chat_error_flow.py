"""MCP 빈 결과·query error·malformed payload·timeout의 HTTP 매핑 계약."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from tests.integration.chat_fakes import build_fake_application, database_success, document_success
from tests.auth_helpers import login


@pytest.mark.integration
@pytest.mark.parametrize(
    ("question", "response", "expected_status", "expected_code", "expected_tool"),
    [
        (
            "휴가 규정 알려줘",
            {"status": "success", "domain": "document", "message": None, "data": [], "sources": [], "metadata": {}},
            200,
            None,
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
        login(client)
        result = client.post("/api/chat", json={"question": question})

    assert result.status_code == expected_status
    if expected_code is None:
        assert result.json()["evidence_status"] == "INSUFFICIENT"
    else:
        assert result.json()["error_code"] == expected_code
    # docs/interface.md 계약: INSUFFICIENT면 원래 route의 retrieval을 정확히 한 번
    # 재시도한다(DOCUMENT도 예외 아님). 그래서 evidence_status를 검사하는 케이스(빈
    # 문서 검색 결과)는 도구가 2번 불리고, 그 외 명시적 오류 케이스는 evidence_eval까지
    # 못 가고 바로 예외로 끝나므로 1번만 불린다.
    expected_call_count = 2 if expected_code is None else 1
    assert [call.tool_name for call in port.calls] == [expected_tool] * expected_call_count
    assert llm.calls == []


@pytest.mark.integration
def test_insufficient_evidence_retries_once_then_returns_safe_response() -> None:
    """저품질 evidence를 정상 답변으로 가장하지 않고, 한 번만 보강 조회한 뒤 종료한다.

    docs/interface.md 계약: INSUFFICIENT면 원래 route의 retrieval을 정확히 한 번
    재시도한다. 무한 재조회를 막기 위해 두 번째도 INSUFFICIENT면 더 이상 재시도하지
    않고 그 상태 그대로 응답한다.
    """
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
        login(client)
        response = client.post("/api/chat", json={"question": "휴가 규정 알려줘"})

    assert response.status_code == 200
    assert response.json()["evidence_status"] == "INSUFFICIENT"
    assert response.json()["sources"] == []
    # 원래 검색어가 동의어 확장 트리거에 안 걸리는 질문이라(query_expansion 없음),
    # 재시도 1회 = document_search가 정확히 2번 불린다.
    assert [call.tool_name for call in port.calls] == ["search_documents", "search_documents"]
    assert llm.calls == []