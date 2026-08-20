"""인증 API 응답과 내부 세션 식별자를 만드는 순수 서비스 함수."""

from __future__ import annotations

import hashlib
import hmac
from typing import TypedDict, cast

from shared.auth_policy import Role, allowed_databases


class UserProfile(TypedDict):
    user_id: int
    username: str
    display_name: str
    role: Role
    allowed_databases: list[str]


def serialize_user(user: object) -> UserProfile:
    """Django 사용자에서 공개 가능한 프로필 필드만 직렬화한다."""
    role = cast(Role, getattr(user, "role"))
    if role not in ("admin", "hr", "finance"):
        raise ValueError("지원하지 않는 계정 역할입니다.")
    return {
        "user_id": int(getattr(user, "pk")),
        "username": str(getattr(user, "username")),
        "display_name": str(getattr(user, "display_name")),
        "role": role,
        "allowed_databases": allowed_databases(role),
    }


def opaque_session_id(session_key: str, introspection_key: str) -> str:
    """Django 세션 원문을 노출하지 않는 서비스 간 식별자를 만든다."""
    return hmac.new(
        introspection_key.encode("utf-8"),
        session_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
