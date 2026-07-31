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
    ...
