"""별도 ACL 기반 Document MCP 스켈레톤의 후보 필터 경계.

공식 document_tools 흐름과 병존하지만 현재 아키텍처 문서에는 이 패키지의 채택
여부와 user_context 전달 계약이 확정돼 있지 않다.
"""

from __future__ import annotations

from typing import Any

from app.core.security import UserContext


def filter_allowed(
    documents: list[dict[str, Any]],
    user_context: UserContext,
) -> list[dict[str, Any]]:
    """검색 후보 중 현재 사용자가 읽을 수 있는 문서/청크만 반환한다.

    tenant_id와 role/permissions를 모두 정책에 따라 검사하고, allowed_roles가 없거나 형식이
    손상된 후보는 기본 거부한다. 입력 순서와 원본 객체를 보존하며, 필터링 사실은 감사용
    메타데이터로만 남기고 비허용 문서의 내용은 노출하지 않는다.
    """
    # TODO(contract clarification): tenant/role/permission의 우선순위와 allowed_roles가
    # 없는 경우의 정책을 확정한다. 확정 전 기본 허용이나 다른 tenant fallback을
    # 추가하지 않으며 ACL·cache 격리 fake test를 완료 조건으로 둔다.
    ...
