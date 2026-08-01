from __future__ import annotations

import time
from typing import Any

from mcp_servers.data_tools.sales.mysql import query_readonly
from mcp_servers.data_tools.sales.schema import get_schema_resource
from mcp_servers.data_tools.sales.text2sql import generate_sql


async def query_sales(question: str) -> list[dict[str, Any]]:
    """판매 질문을 Text2SQL → read-only 조회 순서로 처리한다."""
    schema = get_schema_resource()
    sql = await generate_sql(question, schema)

    started_at = time.time()
    try:
        rows = query_readonly(sql)
        error = None
    except Exception as exc:  # noqa: BLE001
        rows = []
        error = str(exc)
    elapsed_ms = round((time.time() - started_at) * 1000, 1)

    return [
        {
            "type": "database",
            "domain": "sales",
            "generated_sql": sql,
            "row_count": len(rows),
            "rows": rows,
            "elapsed_ms": elapsed_ms,
            "error": error,
        }
    ]
