"""Host MCP client의 envelope 정규화와 오류 분류 contract test."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.mcp.client import (
    FakeMCPPort,
    MCPEvidenceInsufficientError,
    MCPClient,
    MCPInternalError,
    MCPInvalidInputError,
    MCPMalformedPayloadError,
    MCPNoResultError,
    MCPQueryError,
    MCPTimeoutError,
)
from mcp_servers.data_tools.purchase.mysql import ReadOnlyMySQLClient as PurchaseMySQLClient
from mcp_servers.data_tools.sales.mysql import ReadOnlyMySQLClient as SalesMySQLClient
from mcp_servers.data_tools.server import _execute_query
from tests.auth_helpers import TEST_ADMIN_CONTEXT


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
        ({"status": "error", "domain": "purchase", "message": "잘못된 입력", "error_code": "INVALID_INPUT"}, MCPInvalidInputError),
        ({"status": "error", "domain": "purchase", "message": "근거 부족", "error_code": "EVIDENCE_INSUFFICIENT"}, MCPEvidenceInsufficientError),
        ({"status": "error", "domain": "purchase", "message": "내부 오류", "error_code": "INTERNAL_ERROR"}, MCPInternalError),
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


def test_data_tool_preserves_domain_metadata() -> None:
    async def query(_: str) -> list[dict[str, Any]]:
        return [{
            "domain": "sales",
            "rows": [{"order_month": "2026-01", "total_sales": 1200}],
            "generated_sql": "SELECT total_sales",
            "elapsed_ms": 1.2,
            "metadata": {"chart_hint": "line", "currency": "JOD", "views_used": ["v_sales_order"]},
        }]

    envelope = asyncio.run(_execute_query("sales", "월별 매출", query, TEST_ADMIN_CONTEXT))

    assert envelope["metadata"]["chart_hint"] == "line"
    assert envelope["metadata"]["currency"] == "JOD"
    assert envelope["metadata"]["row_count"] == 1


def test_data_tool_preserves_specific_empty_result_message() -> None:
    async def query(_: str) -> list[dict[str, Any]]:
        return [{
            "domain": "sales", "rows": [], "generated_sql": "SELECT total_sales",
            "message": "요청한 지표는 판매 데이터로 계산할 수 없습니다.", "metadata": {},
        }]

    envelope = asyncio.run(_execute_query("sales", "영업이익", query, TEST_ADMIN_CONTEXT))

    assert envelope["error_code"] == "NO_RESULT"
    assert envelope["message"] == "요청한 지표는 판매 데이터로 계산할 수 없습니다."


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


def test_data_server_wraps_purchase_rows_in_common_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    """공식 구매 service 결과가 Host가 검증할 envelope로 변환되게 한다."""
    from mcp_servers.data_tools import server

    original_execute_data_tool = server.execute_data_tool

    async def authorized_execute(tool_name: str, question: str) -> dict[str, Any]:
        return await original_execute_data_tool(tool_name, question, TEST_ADMIN_CONTEXT)

    monkeypatch.setattr(server, "execute_data_tool", authorized_execute)

    async def fake_query(question: str) -> list[dict[str, Any]]:
        assert question == "구매 현황"
        return [{
            "type": "database", "domain": "purchase", "generated_sql": "SELECT 1",
            "row_count": 1, "rows": [{"amount": 100}], "elapsed_ms": 1.0,
        }]

    monkeypatch.setattr(server, "run_purchase_query", fake_query)
    result = asyncio.run(server.execute_data_tool("query_purchase", "구매 현황"))

    assert result["status"] == "success"
    assert result["domain"] == "purchase"
    assert result["data"] == [{"amount": 100}]
    assert result["metadata"]["generated_sql"] == "SELECT 1"


def test_data_server_distinguishes_empty_and_query_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """빈 결과와 provider 실패가 서로 다른 표준 오류로 유지되게 한다."""
    from mcp_servers.data_tools import server

    original_execute_data_tool = server.execute_data_tool

    async def authorized_execute(tool_name: str, question: str) -> dict[str, Any]:
        return await original_execute_data_tool(tool_name, question, TEST_ADMIN_CONTEXT)

    monkeypatch.setattr(server, "execute_data_tool", authorized_execute)

    async def empty_query(_: str) -> list[dict[str, Any]]:
        return [{"domain": "sales", "generated_sql": "SELECT 1", "rows": []}]

    monkeypatch.setattr(server, "run_sales_query", empty_query)
    empty = asyncio.run(server.execute_data_tool("query_sales", "판매 현황"))

    async def failed_query(_: str) -> list[dict[str, Any]]:
        raise RuntimeError("private provider detail")

    monkeypatch.setattr(server, "run_sales_query", failed_query)
    failed = asyncio.run(server.execute_data_tool("query_sales", "판매 현황"))

    assert empty["error_code"] == "NO_RESULT"
    assert failed["error_code"] == "QUERY_ERROR"
    assert "private provider detail" not in str(failed)


@pytest.mark.parametrize(
    "client_type",
    [
        pytest.param(PurchaseMySQLClient, id="purchase"),
        pytest.param(SalesMySQLClient, id="sales"),
    ],
)
@pytest.mark.parametrize("sql", ["UPDATE orders SET status='x'", "SELECT 1; SELECT 2", "SELECT /* bypass */ 1"])
def test_domain_mysql_clients_reject_non_single_select_before_connect(
    client_type: type,
    sql: str,
) -> None:
    """공식 purchase/sales adapter가 쓰기·다중·주석 SQL을 DB 연결 전에 거부한다."""
    client = client_type("host", "user", "password", "database")

    with pytest.raises(ValueError):
        client.query(sql)


def test_data_mcp_server_can_register_official_domain_tools() -> None:
    """MCP server 조립이 import만 성공하는 스켈레톤으로 퇴행하지 않게 한다."""
    from mcp_servers.data_tools.server import create_server

    assert create_server() is not None
