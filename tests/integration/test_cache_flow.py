import pytest
from fastapi.testclient import TestClient

from app.mcp.client import MCPNoResultError, MCPQueryError
from tests.integration.chat_fakes import build_fake_application, database_success, document_success


@pytest.mark.integration
def test_both_success_is_cached_without_additional_port_or_llm_calls() -> None:
    application, port, llm = build_fake_application(
        {
            "search_documents": document_success(),
            "query_purchase": database_success("purchase", 100),
            "query_sales": database_success("sales", 200),
        }
    )

    with TestClient(application) as client:
        first = client.post("/api/chat", json={"question": "휴가 규정과 매출 알려줘"})
        calls_after_miss = list(port.calls)
        llm_calls_after_miss = list(llm.calls)
        second = client.post("/api/chat", json={"question": "휴가 규정과 매출 알려줘"})

    assert first.status_code == 200
    assert first.json()["route"] == "BOTH"
    assert {source["source_type"] for source in first.json()["sources"]} == {"document", "database"}
    assert [call.tool_name for call in calls_after_miss] == ["search_documents", "query_sales"]
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert port.calls == calls_after_miss
    assert llm.calls == llm_calls_after_miss


@pytest.mark.integration
def test_both_keeps_document_result_when_database_tool_fails() -> None:
    application, port, llm = build_fake_application(
        {
            "search_documents": document_success(),
            "query_purchase": database_success("purchase", 100),
            "query_sales": MCPQueryError("query_sales", "database unavailable"),
        }
    )

    with TestClient(application) as client:
        response = client.post("/api/chat", json={"question": "휴가 규정과 매출 알려줘"})

    body = response.json()
    assert response.status_code == 200
    assert body["cached"] is False
    assert [source["source_type"] for source in body["sources"]] == ["document"]
    assert "일부 근거" in body["answer"]
    assert [call.tool_name for call in port.calls] == ["search_documents", "query_sales"]
    assert len(llm.calls) == 1


@pytest.mark.integration
def test_both_returns_insufficient_response_when_all_tools_fail() -> None:
    application, port, llm = build_fake_application(
        {
            "search_documents": MCPNoResultError("search_documents", "not found"),
            "query_purchase": database_success("purchase", 100),
            "query_sales": MCPQueryError("query_sales", "database unavailable"),
        }
    )

    with TestClient(application) as client:
        response = client.post("/api/chat", json={"question": "휴가 규정과 매출 알려줘"})

    body = response.json()
    assert response.status_code == 200
    assert body["cached"] is False
    assert body["sources"] == []
    assert body["tables"] == []
    assert "근거를 찾지 못해" in body["answer"]
    assert [call.tool_name for call in port.calls] == ["search_documents", "query_sales"]
    assert llm.calls == []
