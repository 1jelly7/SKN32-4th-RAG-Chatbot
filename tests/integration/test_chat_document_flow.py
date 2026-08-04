"""FastAPI→Graph→fake Document MCP→응답 직렬화의 mock 통합 계약."""

import pytest
from fastapi.testclient import TestClient

from tests.integration.chat_fakes import build_fake_application, database_success, document_success
from tests.auth_helpers import login


@pytest.mark.integration
def test_document_question_flows_from_api_to_document_fake_and_response() -> None:
    """문서 route가 공개 출처를 보존하고 내부 file_path를 노출하지 않게 한다."""
    application, port, llm = build_fake_application(
        {
            "search_documents": document_success(),
            "query_purchase": database_success("purchase", 100),
            "query_sales": database_success("sales", 200),
        }
    )

    with TestClient(application) as client:
        login(client)
        response = client.post("/api/chat", json={"question": "휴가 규정 알려줘"})

    body = response.json()
    assert response.status_code == 200
    assert body["route"] == "DOCUMENT"
    assert body["cached"] is False
    assert body["answer"] == "fake answer"
    assert body["sources"] == [
        {
            "id": "policy-001",
            "title": "휴가 규정",
            "source_type": "document",
            "document_id": "policy-001",
            "file_name": "휴가 규정",
            "score": 0.9,
            "page": None,
            "pages": [3],
            "chunks": [{"page": 3, "text": "휴가 규정은 승인 절차를 따릅니다."}],
            "download_url": "/api/documents/download?doc_id=policy-001",
            "updated_at": None,
            "table_name": None,
            "query_id": None,
            "freshness_seconds": None,
            "source_version": "fixture-index-v1",
        }
    ]
    assert [call.tool_name for call in port.calls] == ["search_documents"]
    assert len(llm.calls) == 1
    assert "file_path" not in response.text
