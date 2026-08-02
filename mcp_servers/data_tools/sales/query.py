"""판매 자연어 질의를 Text2SQL과 읽기 전용 조회로 연결하는 도메인 서비스."""

from __future__ import annotations

import time
from typing import Any

from mcp_servers.data_tools.sales.mysql import query_readonly
from mcp_servers.data_tools.sales.schema import get_schema_resource
from mcp_servers.data_tools.sales.text2sql import generate_sql


async def query_sales(question: str) -> list[dict[str, Any]]:
    """판매 질문을 Text2SQL → read-only 조회 순서로 처리한다.

    서버가 공통 envelope로 감싸기 전의 내부 database evidence를 반환한다. 판매 질문에만
    사용하며 쓰기 SQL, ETL, 구매 테이블 조회를 수행하지 않는다.
    """
    schema = get_schema_resource()
    sql = await generate_sql(question, schema)

    started_at = time.time()
    rows = query_readonly(sql)
    elapsed_ms = round((time.time() - started_at) * 1000, 1)

    return [
        {
            "type": "database",
            "domain": "sales",
            "generated_sql": sql,
            "row_count": len(rows),
            "rows": rows,
            "elapsed_ms": elapsed_ms,
        }
    ]
