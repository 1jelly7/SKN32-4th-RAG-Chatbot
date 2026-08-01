"""범용 schema·SQL guard·read-only 실행을 조합하려는 Data MCP 스켈레톤."""

from __future__ import annotations

from typing import Any

from app.core.security import UserContext


async def query_business_data(
    question: str,
    user_context: UserContext,
) -> list[dict[str, Any]]:
    """Data MCP의 자연어 업무 조회 전체 흐름을 수행한다.

    schema resource를 읽고 generate_sql로 초안을 만든 다음 SQL Guard로 단일 SELECT,
    allowlist, LIMIT, 금지 키워드를 확인한다. 이후 user_context의 tenant/권한 필터를
    강제해 read-only MySQL에서 실행하고, 행 수 제한과 SQL 요약·실행 시각을 포함한
    근거 형식으로 반환한다. 어느 단계에서도 쓰기 SQL을 실행하지 않는다.
    """
    # TODO(contract clarification): 정식 purchase/sales Tool과 이 범용 query의 공개 이름,
    # user_context/tenant 전달 방식, evidence→envelope 변환 소유자를 확정한다. 구현 시
    # schema→generate→guard→read-only query 순서와 단계별 실패를 fake로 검증한다.
    ...
