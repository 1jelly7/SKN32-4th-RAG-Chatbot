from __future__ import annotations

from typing import Any


async def query_purchase(
    question: str,
) -> list[dict[str, Any]]:
    """구매 자연어 업무 조회 전체 흐름을 수행한다.

    schema resource를 읽고 generate_sql로 SELECT 초안을 만든 뒤 read-only MySQL에서
    실행한다. 결과 행과 SQL 요약·실행 시각을 근거 형식으로 반환한다.
    """
    ...
