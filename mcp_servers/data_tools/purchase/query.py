"""구매 자연어 질의를 Text2SQL과 읽기 전용 조회로 연결하는 도메인 서비스.

처리 순서: 입력 검증 -> LLM SQL 생성 -> 정적 가드 -> EXPLAIN 사전검증 ->
(실패 시 오류를 보여주고 1회만 재작성) -> 실제 실행 -> 결과 정리.
답할 수 없는 질문은 SQL을 만들지 않고 빈 결과를 반환해 server.py가
NO_RESULT로 처리하게 한다. (mcp_servers/data_tools/sales/query.py와 동일 패턴)
"""

from __future__ import annotations

import time
from typing import Any

from mcp_servers.data_tools.purchase.mysql import explain_readonly, query_readonly
from mcp_servers.data_tools.purchase.schema import get_schema_resource
from mcp_servers.data_tools.purchase.sql_guard import ALLOWED_VIEWS, referenced_tables, validate_and_normalize
from mcp_servers.data_tools.purchase.text2sql import generate_sql, generate_sql_with_error

MAX_QUESTION_LENGTH = 500


def _empty_evidence(generated_sql: str, elapsed_ms: float, retry_count: int) -> list[dict[str, Any]]:
    """rows=[]로 반환해 server.py가 NO_RESULT 오류로 처리하게 한다."""
    return [
        {
            "type": "database",
            "domain": "purchase",
            "generated_sql": generated_sql,
            "row_count": 0,
            "rows": [],
            "elapsed_ms": elapsed_ms,
            "metadata": {
                "views_used": [],
                "retry_count": retry_count,
            },
        }
    ]


async def query_purchase(question: str) -> list[dict[str, Any]]:
    """구매 질문을 Text2SQL -> 가드 -> EXPLAIN -> read-only 조회 순서로 처리한다.

    서버가 공통 envelope로 감싸기 전의 내부 database evidence를 반환한다. 구매 질문에만
    사용하며 쓰기 SQL, ETL, 판매 테이블 조회를 수행하지 않는다.
    """
    started_at = time.monotonic()
    question = question.strip()

    if not question or len(question) > MAX_QUESTION_LENGTH:
        return _empty_evidence("", round((time.monotonic() - started_at) * 1000, 1), retry_count=0)

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
    if not sql:
        # LLM이 뷰·용어집으로 답할 수 없다고 판단했다(NO_SQL) — 범위 밖/모호한 질문.
        elapsed_ms = round((time.monotonic() - started_at) * 1000, 1)
        return _empty_evidence("", elapsed_ms, retry_count=0)

    retry_count = 0
    try:
        normalized = validate_and_normalize(sql)
        explain_readonly(normalized)
    except Exception as exc:  # noqa: BLE001 - 가드/EXPLAIN 실패는 재작성 신호일 뿐이다.
        retry_count = 1
        retried_sql = await generate_sql_with_error(question, schema, sql, str(exc))
        if not retried_sql:
            elapsed_ms = round((time.monotonic() - started_at) * 1000, 1)
            return _empty_evidence(sql, elapsed_ms, retry_count=retry_count)
        # 재시도 결과도 검증한다. 여기서 또 실패하면 예외를 그대로 올려
        # server.py가 QUERY_ERROR로 변환하게 한다(재시도는 최대 1회로 제한).
        sql = retried_sql
        normalized = validate_and_normalize(sql)
        explain_readonly(normalized)

    rows = query_readonly(normalized)
    elapsed_ms = round((time.monotonic() - started_at) * 1000, 1)

    views_used = sorted(referenced_tables(normalized) & ALLOWED_VIEWS)

    return [
        {
            "type": "database",
            "domain": "purchase",
            "generated_sql": normalized,
            "row_count": len(rows),
            "rows": rows,
            "elapsed_ms": elapsed_ms,
            "metadata": {
                "views_used": views_used,
                "retry_count": retry_count,
            },
        }
    ]

