import pytest
from fastapi.testclient import TestClient

from tests.integration.chat_fakes import build_fake_application, database_success, document_success


@pytest.mark.integration
@pytest.mark.parametrize(
    ("question", "expected_domain", "expected_tool"),
    [
        ("공급업체별 구매 지출 알려줘", "purchase", "query_purchase"),
        ("고객별 매출 알려줘", "sales", "query_sales"),
    ],
)
def test_single_domain_database_questions_call_only_the_selected_tool(
    question: str, expected_domain: str, expected_tool: str
) -> None:
    application, port, llm = build_fake_application(
        {
            "search_documents": document_success(),
            "query_purchase": database_success("purchase", 100),
            "query_sales": database_success("sales", 200),
        }
    )

    with TestClient(application) as client:
        response = client.post("/api/chat", json={"question": question})

    body = response.json()
    assert response.status_code == 200
    assert body["route"] == "DATABASE"
    assert body["sources"][0]["source_type"] == "database"
    assert body["sources"][0]["id"] == f"{expected_domain}-sql"
    assert body["tables"][0]["domain"] == expected_domain
    assert [call.tool_name for call in port.calls] == [expected_tool]
    assert len(llm.calls) == 1


@pytest.mark.integration
def test_ambiguous_database_question_calls_purchase_and_sales() -> None:
    application, port, llm = build_fake_application(
        {
            "search_documents": document_success(),
            "query_purchase": database_success("purchase", 100),
            "query_sales": database_success("sales", 200),
        }
    )

    with TestClient(application) as client:
        response = client.post("/api/chat", json={"question": "이번 분기 실적 알려줘"})

    body = response.json()
    assert response.status_code == 200
    assert body["route"] == "DATABASE"
    assert [source["id"] for source in body["sources"]] == ["purchase-sql", "sales-sql"]
    assert [table["domain"] for table in body["tables"]] == ["purchase", "sales"]
    assert [call.tool_name for call in port.calls] == ["query_purchase", "query_sales"]
    assert len(llm.calls) == 1
