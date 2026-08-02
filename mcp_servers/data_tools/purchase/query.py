"""구매 자연어 질문을 Text2SQL과 읽기 전용 조회로 연결한다."""

from __future__ import annotations

import time
from typing import Any

from mcp_servers.data_tools.purchase.mysql import query_readonly
from mcp_servers.data_tools.purchase.schema import get_schema_resource
from mcp_servers.data_tools.purchase.text2sql import generate_sql


async def query_purchase(question: str) -> list[dict[str, Any]]:
    """구매 질문을 SELECT로 변환해 실행하고 provenance가 있는 evidence를 반환한다.

    빈 결과는 빈 rows를 가진 evidence로 반환하며, SQL 생성·검증·DB 오류는 공통 Data
    MCP server가 표준 오류 envelope로 변환할 수 있도록 그대로 전파한다.
    """
    schema = get_schema_resource()
    sql = await generate_sql(question, schema)
    started_at = time.monotonic()
    rows = query_readonly(sql)
    return [{
        "type": "database",
        "domain": "purchase",
        "generated_sql": sql,
        "row_count": len(rows),
        "rows": rows,
        "elapsed_ms": round((time.monotonic() - started_at) * 1000, 1),
    }]
