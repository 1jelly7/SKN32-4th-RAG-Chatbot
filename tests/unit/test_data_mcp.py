"""Host MCP client의 envelope 정규화와 오류 분류 contract test."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.mcp.client import (
    FakeMCPPort,
    MCPClient,
    MCPMalformedPayloadError,
    MCPNoResultError,
    MCPQueryError,
    MCPTimeoutError,
)


def _success(
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


def test_data_query_normalizes_purchase_and_sales_and_records_calls() -> None:
    port = FakeMCPPort(
        {
            "search_documents": _success("document", []),
            "query_purchase": _success("purchase", [{"vendor": "A사", "amount": 100}], metadata={"generated_sql": "SELECT amount"}),
            "query_sales": _success("sales", [{"customer": "B사", "revenue": 200}], metadata={"generated_sql": "SELECT revenue"}),
        }
    )
    client = MCPClient(port)

    evidence = asyncio.run(client.data_query("both", "구매와 판매 현황"))

    assert [item["domain"] for item in evidence] == ["purchase", "sales"]
    assert [call.tool_name for call in port.calls] == ["query_purchase", "query_sales"]
    assert port.calls[0].payload == {"question": "구매와 판매 현황"}


def test_document_search_normalizes_data_and_sources() -> None:
    port = FakeMCPPort(
        {
            "search_documents": _success(
                "document",
                [{"content": "휴가 신청 절차", "score": 0.9}],
                [{"document_id": "policy-1", "title": "휴가 규정", "page": 3}],
            ),
            "query_purchase": _success("purchase", []),
            "query_sales": _success("sales", []),
        }
    )

    evidence = asyncio.run(MCPClient(port).document_search("휴가", 3))

    assert evidence == [{"type": "document", "document_id": "policy-1", "title": "휴가 규정", "content": "휴가 신청 절차", "score": 0.9, "page": 3, "metadata": {}}]
    assert len(port.calls) == 1
    assert port.calls[0].tool_name == "search_documents"
    assert port.calls[0].payload == {"query": "휴가", "top_k": 3}


@pytest.mark.parametrize(
    ("response", "error_type"),
    [
        ("not-an-envelope", MCPMalformedPayloadError),
        (_success("sales", []), MCPMalformedPayloadError),
        ({"status": "error", "domain": "purchase", "message": "결과 없음", "error_code": "NO_RESULT"}, MCPNoResultError),
        ({"status": "error", "domain": "purchase", "message": "실패", "error_code": "QUERY_ERROR"}, MCPQueryError),
        (asyncio.TimeoutError(), MCPTimeoutError),
    ],
)
def test_purchase_query_distinguishes_mcp_errors(response: object, error_type: type[Exception]) -> None:
    """malformed, NO_RESULT, QUERY_ERROR, timeout이 서로 다른 내부 예외로 유지되게 한다."""
    port = FakeMCPPort(
        {
            "search_documents": _success("document", []),
            "query_purchase": response,
            "query_sales": _success("sales", []),
        }
    )

    with pytest.raises(error_type):
        asyncio.run(MCPClient(port, timeout_seconds=0.01).purchase_query("구매 현황"))


def test_fake_mcp_returns_defensive_response_copy() -> None:
    """fake 결과 변형이 production fixture 의미를 오염시키지 않게 한다."""
    response = _success("purchase", [{"amount": 100}])
    port = FakeMCPPort(
        {
            "search_documents": _success("document", []),
            "query_purchase": response,
            "query_sales": _success("sales", []),
        }
    )

    evidence = asyncio.run(MCPClient(port).purchase_query("구매 현황"))
    evidence[0]["rows"][0]["amount"] = 999

    assert response["data"][0]["amount"] == 100


@pytest.mark.parametrize(
    ("tool_name", "method"),
    [
        ("search_documents", "document_search"),
        ("query_purchase", "purchase_query"),
    ],
)
def test_success_envelope_with_empty_data_is_no_result(
    tool_name: str,
    method: str,
) -> None:
    port = FakeMCPPort(
        {
            "search_documents": _success("document", []),
            "query_purchase": _success("purchase", []),
            "query_sales": _success("sales", [{"revenue": 1}]),
        }
    )
    client = MCPClient(port)

    with pytest.raises(MCPNoResultError):
        if method == "document_search":
            asyncio.run(client.document_search("휴가", 3))
        else:
            asyncio.run(client.purchase_query("구매 현황"))

    assert port.calls[0].tool_name == tool_name
    assert port.calls[0].payload
