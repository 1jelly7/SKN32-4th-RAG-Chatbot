"""구매·판매 조회를 공통 MCP envelope로 공개하는 Data MCP 경계."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

from mcp_servers.data_tools.purchase.query import query_purchase as run_purchase_query
from mcp_servers.data_tools.sales.query import query_sales as run_sales_query

DataToolName = Literal["query_purchase", "query_sales"]
DomainQuery = Callable[[str], Awaitable[list[dict[str, Any]]]]


def _error_envelope(domain: str, code: str, message: str) -> dict[str, Any]:
    """내부 예외 상세 없이 표준 Data Tool 오류를 만든다."""
    return {
        "status": "error",
        "domain": domain,
        "message": message,
        "error_code": code,
        "data": [],
        "sources": [],
        "metadata": {},
    }


async def _execute_query(domain: str, question: str, query: DomainQuery) -> dict[str, Any]:
    """도메인 service 결과를 공통 success/error envelope로 변환한다."""
    if not question or not question.strip():
        return _error_envelope(domain, "INVALID_INPUT", "질문이 비어 있습니다.")
    try:
        evidence = await query(question)
    except Exception:  # noqa: BLE001 - provider 상세를 외부 envelope에 노출하지 않는다.
        return _error_envelope(domain, "QUERY_ERROR", "업무 데이터 조회에 실패했습니다.")

    if len(evidence) != 1 or evidence[0].get("domain") != domain:
        return _error_envelope(domain, "INTERNAL_ERROR", "조회 결과 형식이 올바르지 않습니다.")

    result = evidence[0]
    rows = result.get("rows")
    generated_sql = result.get("generated_sql")
    if not isinstance(rows, list) or not isinstance(generated_sql, str):
        return _error_envelope(domain, "INTERNAL_ERROR", "조회 결과 형식이 올바르지 않습니다.")
    if not rows:
        return _error_envelope(domain, "NO_RESULT", "조회 가능한 결과가 없습니다.")

    return {
        "status": "success",
        "domain": domain,
        "message": None,
        "data": rows,
        "sources": [],
        "metadata": {
            "generated_sql": generated_sql,
            "row_count": len(rows),
            "elapsed_ms": result.get("elapsed_ms"),
        },
    }


async def execute_data_tool(tool_name: DataToolName, question: str) -> dict[str, Any]:
    """Host transport와 MCP server가 공유하는 도메인 Tool dispatch를 수행한다."""
    if tool_name == "query_purchase":
        return await _execute_query("purchase", question, run_purchase_query)
    if tool_name == "query_sales":
        return await _execute_query("sales", question, run_sales_query)
    raise ValueError(f"지원하지 않는 Data MCP Tool입니다: {tool_name}")


def create_server() -> MCPServer:
    """읽기 전용 구매·판매 Tool을 등록한 Data MCP server를 만든다."""
    server = MCPServer(name="data-mcp", version="0.1.0")

    @server.tool()
    async def query_purchase(question: str) -> dict[str, Any]:
        """구매·지출·공급업체 질문에만 사용하고 표준 purchase envelope를 반환한다."""
        return await execute_data_tool("query_purchase", question)

    @server.tool()
    async def query_sales(question: str) -> dict[str, Any]:
        """판매·매출·고객 질문에만 사용하고 표준 sales envelope를 반환한다."""
        return await execute_data_tool("query_sales", question)

    return server


def main() -> None:
    """설정을 검증한 뒤 Data MCP transport를 시작한다."""
    from app.core.config import get_settings

    get_settings()
    create_server().run()


if __name__ == "__main__":
    main()
