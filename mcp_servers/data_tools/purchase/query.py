"""구매 자연어 질의를 처리할 미구현 도메인 서비스 경계."""

from __future__ import annotations

from typing import Any


async def query_purchase(
    question: str,
) -> list[dict[str, Any]]:
    """구매 자연어 업무 조회 전체 흐름을 수행한다.

    schema resource를 읽고 generate_sql로 SELECT 초안을 만든 뒤 read-only MySQL에서
    실행한다. 결과 행과 SQL 요약·실행 시각을 근거 형식으로 반환한다.
    """
    # TODO(implementation): 구매 schema→Text2SQL→SELECT guard→read-only MySQL 순서로
    # 실행하고 rows, generated_sql, row_count, table/query/freshness metadata가 있는
    # 내부 evidence를 반환한다. 공통 server가 success/error envelope로 변환하기 전에
    # 빈 결과와 QUERY_ERROR를 구분하며 판매 DB나 ETL을 호출하지 않는다.
    # Completion criteria:
    # - 구매 Tool fake로 success, empty result, query error, timeout을 검증한다.
    # - SELECT 외 SQL과 미허용 table을 실행 전에 거부한다.
    # - domain="purchase"와 provenance metadata를 보존한다.
    ...
