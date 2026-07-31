from __future__ import annotations

import time
from typing import Any

from mcp_servers.data_tools.finance.mysql import query_readonly
from mcp_servers.data_tools.finance.schema import get_schema_resource
from mcp_servers.data_tools.finance.text2sql import generate_sql


async def query_finance(
    question: str,
) -> list[dict[str, Any]]:
    """재무(구매/지출) 자연어 업무 조회 전체 흐름을 수행한다.

    schema resource를 읽고 generate_sql로 SELECT 초안을 만든 뒤 read-only MySQL에서
    실행한다. 결과 행과 SQL 요약·실행 시각을 근거 형식으로 반환한다.
    """
    schema = get_schema_resource()
    sql = await generate_sql(question, schema)

    started_at = time.time()
    try:
        rows = query_readonly(sql)
        error = None
    except Exception as exc:  # noqa: BLE001 - 근거 형식으로 오류를 함께 반환합니다.
        rows = []
        error = str(exc)
    elapsed_ms = round((time.time() - started_at) * 1000, 1)

    return [
        {
            "type": "database",
            "domain": "finance",
            "generated_sql": sql,
            "row_count": len(rows),
            "rows": rows,
            "elapsed_ms": elapsed_ms,
            "error": error,
        }
    ]
