"""인증 계층이 제공할 최소 사용자 context의 미구현 검증 경계.

현재 공개 ChatRequest와 MCP Tool 계약에는 user_context 전달 방식이 확정돼 있지 않다.
권한·tenant 정보는 사용자 본문에서 신뢰하지 않으며 계약 확정 전 기본 허용하지 않는다.
"""

from __future__ import annotations

from typing import Any, TypedDict


class UserContext(TypedDict):
    """인증 계층이 보증해야 하는 주체·tenant·권한의 최소 표현."""

    user_id: str
    role: str
    tenant_id: str
    permissions: list[str]


def build_user_context(
    user_id: str,
    role: str,
    tenant_id: str,
    permissions: list[str],
) -> UserContext:
    """인증된 주체 정보에서 최소 권한 UserContext를 만든다.

    user_id/tenant_id/role의 비어 있음과 permissions 형식을 검증하고, 권한 목록은 중복을
    제거해 안정적으로 정렬한다. 이 함수의 입력은 인증 계층이 보장한 값이어야 하며,
    HTTP 본문의 self-asserted role을 그대로 신뢰하는 용도로 사용하면 안 된다.
    """
    # TODO(contract clarification): 허용 role/permission 목록과 인증 주체→MCP 전달 방식을
    # 확정한 뒤 빈 값, 중복 권한, 알 수 없는 권한을 fail closed로 검증한다. tenant별
    # cache key 격리와 ACL fake coverage도 완료 조건이다.
    ...


def validate_user_context(context: dict[str, Any]) -> UserContext:
    """외부에서 받은 context를 엄격히 검증·정규화해 UserContext로 반환한다.

    필수 키·자료형·빈 값·알 수 없는 권한을 검사하고 불완전한 컨텍스트는 명시적으로
    거절한다. 테넌트와 역할 범위를 넓혀 주는 기본값을 넣지 않아야 ACL과 캐시 격리가
    무너지지 않는다.
    """
    # TODO(contract clarification): 필수 키와 허용 permission registry를 확정한 뒤 엄격히
    # 검증한다. 누락값에 광범위한 기본 권한을 넣지 않는다.
    ...
