"""판매 자연어 질의를 Text2SQL과 읽기 전용 조회로 연결하는 도메인 서비스.

처리 순서: 입력 검증 -> LLM SQL 생성 -> 정적 가드 -> EXPLAIN 사전검증 ->
(실패 시 오류를 보여주고 1회만 재작성) -> 실제 실행 -> 결과 정리.
답할 수 없는 질문은 SQL을 만들지 않고 빈 결과를 반환해 server.py가
NO_RESULT로 처리하게 한다(친절한 사유 메시지는 공통 envelope 확장 후 과제,
docs/team_share/03_cross_team_requests.md 참고).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from mcp_servers.data_tools.sales.mysql import explain_readonly, query_readonly
from mcp_servers.data_tools.sales.schema import SchemaResource, get_schema_resource
from mcp_servers.data_tools.sales.sql_guard import (
    ALLOWED_VIEWS,
    referenced_tables,
    validate_and_normalize,
)
from mcp_servers.data_tools.sales.text2sql import generate_sql, generate_sql_with_error

MAX_QUESTION_LENGTH = 500
ROW_LIMIT = 200


# old:
# def _empty_evidence(
#     generated_sql: str, elapsed_ms: float, retry_count: int, message: str
# ) -> list[dict[str, Any]]:
#     """빈 결과의 원인과 대안을 공통 envelope까지 전달할 evidence를 만든다."""
#     schema = get_schema_resource()
#     return [
#         {
#             "type": "database",
#             "domain": "sales",
#             "generated_sql": generated_sql,
#             "row_count": 0,
#             "rows": [],
#             "elapsed_ms": elapsed_ms,
#             "message": message,
#             "metadata": {
#                 "views_used": [],
#                 "data_coverage": schema["data_coverage"],
#                 "retry_count": retry_count,
#                 "currency": schema["currency"],
#                 "truncated": False,
#                 "chart_hint": None,
#             },
#         }
#     ]
#
# 변경 이유: 복합질문에서는 항목(하위 SELECT)마다 빈 결과 evidence를 하나씩 만들어야
# 해서, dict 조립 자체는 _empty_evidence_item()으로 옮기고 label을 추가했다. 이
# 함수는 항목이 없는 최상단 실패(빈 질문·NO_SQL 전체)에서 기존과 동일하게 그 dict를
# 리스트 1개로 감싸는 역할만 한다.
def _empty_evidence_item(
    label: str,
    schema: SchemaResource,
    generated_sql: str,
    elapsed_ms: float,
    retry_count: int,
    message: str,
) -> dict[str, Any]:
    """빈 결과 항목 1개의 원인과 대안을 evidence dict로 만든다(리스트로 감싸지 않음)."""
    return {
        "type": "database",
        "domain": "sales",
        "label": label,
        "generated_sql": generated_sql,
        "row_count": 0,
        "rows": [],
        "elapsed_ms": elapsed_ms,
        "message": message,
        "metadata": {
            "views_used": [],
            "data_coverage": schema["data_coverage"],
            "retry_count": retry_count,
            "currency": schema["currency"],
            "truncated": False,
            "chart_hint": None,
        },
    }


def _empty_evidence(
    label: str, generated_sql: str, elapsed_ms: float, retry_count: int, message: str
) -> list[dict[str, Any]]:
    """빈 결과의 원인과 대안을 공통 envelope까지 전달할 evidence를 만든다.

    schema가 아직 로드되기 전(빈 질문 등 최상단 검증 실패)에도 불릴 수 있어
    get_schema_resource()를 직접 호출한다.
    """
    schema = get_schema_resource()
    return [_empty_evidence_item(label, schema, generated_sql, elapsed_ms, retry_count, message)]


def _chart_hint(rows: list[dict[str, Any]]) -> str | None:
    """결과 첫 행의 컬럼명으로 막대/꺾은선 중 어느 쪽이 어울릴지 가볍게 추정한다.

    지금은 server.py가 이 값을 그대로 버리지만, docs/team_share/04_chart_spec.md의
    UI 구현이 따라올 때 한 줄만 병합하면 쓸 수 있도록 미리 계산해둔다.
    """
    if not rows:
        return None
    first_keys = rows[0].keys()
    if any(k.endswith(("_month", "_quarter", "_year")) for k in first_keys):
        return "line"
    return "bar"


# 추가: 복합질문의 하위 SELECT 1개를 검증→EXPLAIN→(실패 시 재작성 1회)→실행까지
# 처리하는 헬퍼. old query_sales()에 있던 단일 쿼리 파이프라인을 그대로 옮긴 것으로,
# validate_and_normalize -> explain_readonly -> 실패 시 generate_sql_with_error
# 1회 재작성 -> query_readonly 순서와 판단 로직은 한 글자도 바꾸지 않았다. 항목별로
# 이 함수를 asyncio.gather로 동시에 돌리기 위해 별도 함수로 뺐다.
async def _run_single_query(
    question: str,
    schema: SchemaResource,
    item: dict[str, str],
    started_at: float,
) -> dict[str, Any]:
    """복합질문 하위 항목 1개(label, sql)를 처리해 evidence dict 1개를 만든다."""
    label = item["label"]
    sql = item["sql"]

    retry_count = 0
    try:
        normalized = validate_and_normalize(sql)
        await asyncio.to_thread(explain_readonly, normalized)
    except Exception as exc:  # noqa: BLE001 - 가드/EXPLAIN 실패는 재작성 신호일 뿐이다.
        retry_count = 1
        retried = await generate_sql_with_error(question, schema, sql, str(exc))
        if not retried:
            elapsed_ms = round((time.monotonic() - started_at) * 1000, 1)
            return _empty_evidence_item(
                label,
                schema,
                sql,
                elapsed_ms,
                retry_count,
                "요청 조건을 판매 데이터 조회로 해석할 수 없습니다. 기간·고객·매출 기준을 구체적으로 알려 주세요.",
            )
        # 재시도 결과도 검증한다. 여기서 또 실패하면 예외를 그대로 올려
        # server.py가 QUERY_ERROR로 변환하게 한다(재시도는 최대 1회로 제한).
        # 추가: generate_sql_with_error()도 이제 list[dict]를 반환하지만, 재작성은
        # 실패한 항목 1개를 고치는 것이라 첫 번째 결과만 쓴다.
        sql = retried[0]["sql"]
        normalized = validate_and_normalize(sql)
        await asyncio.to_thread(explain_readonly, normalized)

    rows = await asyncio.to_thread(query_readonly, normalized)
    elapsed_ms = round((time.monotonic() - started_at) * 1000, 1)

    views_used = sorted(referenced_tables(normalized) & ALLOWED_VIEWS)

    if not rows:
        return _empty_evidence_item(
            label,
            schema,
            normalized,
            elapsed_ms,
            retry_count,
            "해당 조건의 판매 데이터가 없습니다. 보유 기간과 조건을 확인해 다시 질문해 주세요.",
        )

    return {
        "type": "database",
        "domain": "sales",
        "label": label,
        "generated_sql": normalized,
        "row_count": len(rows),
        "rows": rows,
        "elapsed_ms": elapsed_ms,
        "metadata": {
            "views_used": views_used,
            "data_coverage": schema["data_coverage"],
            "retry_count": retry_count,
            "currency": schema["currency"],
            "truncated": len(rows) >= ROW_LIMIT,
            "chart_hint": _chart_hint(rows),
        },
    }


async def query_sales(question: str) -> list[dict[str, Any]]:
    """판매 질문을 Text2SQL -> 가드 -> EXPLAIN -> read-only 조회 순서로 처리한다.

    추가: 복합질문이면 Text2SQL이 만든 하위 SELECT(label, sql) 항목마다
    _run_single_query()를 asyncio.gather로 병렬 실행해, 항목 개수만큼 evidence를
    반환한다(BOTH 라우트가 document/database evidence를 병렬로 모으는 것과 같은 패턴).
    서버가 공통 envelope로 감싸기 전의 내부 database evidence를 반환한다. 판매 질문에만
    사용하며 쓰기 SQL, ETL, 구매 테이블 조회를 수행하지 않는다.
    """
    started_at = time.monotonic()
    question = question.strip()

    if not question or len(question) > MAX_QUESTION_LENGTH:
        return _empty_evidence(
            "",
            "",
            round((time.monotonic() - started_at) * 1000, 1),
            retry_count=0,
            message="질문 형식이 올바르지 않습니다. 판매 데이터 범위에서 다시 질문해 주세요.",
        )

    # get_schema_resource()는 최초 1회 내부에서 동기 DB 조회(_load_data_coverage)를
    # 한다. to_thread 없이 직접 호출하면 그 몇 초 동안 이벤트 루프가 멈춰서, BOTH
    # 질문에서 병렬로 같이 돌아야 할 document_retrieval까지 시작을 못 하게 된다.
    schema = await asyncio.to_thread(get_schema_resource)

    # old:
    # sql = await generate_sql(question, schema)
    # if not sql:
    #     # LLM이 뷰·지표로 답할 수 없다고 판단했다(NO_SQL) — 범위 밖/모호한 질문.
    #     elapsed_ms = round((time.monotonic() - started_at) * 1000, 1)
    #     return _empty_evidence(
    #         "", elapsed_ms, retry_count=0,
    #         message="요청한 지표는 판매 데이터로 계산할 수 없습니다. 매출·미수금·주문 기준으로 질문해 주세요.",
    #     )
    # (이하 단일 sql 검증→EXPLAIN→재작성→실행 로직은 _run_single_query()로 이동)
    #
    # 변경 이유: generate_sql()이 이제 최대 MAX_SUB_QUERIES개의 {label, sql} 리스트를
    # 반환한다. 빈 리스트면 기존과 동일하게 NO_SQL(범위 밖) 처리하고, 항목이 있으면
    # 각각을 _run_single_query()에 위임해 병렬로 처리한다.
    queries = await generate_sql(question, schema)
    if not queries:
        elapsed_ms = round((time.monotonic() - started_at) * 1000, 1)
        return _empty_evidence(
            "",
            "",
            elapsed_ms,
            retry_count=0,
            message="요청한 지표는 판매 데이터로 계산할 수 없습니다. 매출·미수금·주문 기준으로 질문해 주세요.",
        )

    results = await asyncio.gather(
        *(_run_single_query(question, schema, item, started_at) for item in queries)
    )
    return list(results)
