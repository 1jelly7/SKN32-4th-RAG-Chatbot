"""인증 저장소와 API가 공유하는 최소 계정 모델이다."""

from __future__ import annotations

from dataclasses import dataclass

from app.auth.policy import Role


@dataclass(frozen=True)
class Account:
    """로그인 검증에만 필요한 계정 레코드이며 API 응답에 해시를 노출하지 않는다."""

    id: int
    username: str
    password_hash: str
    display_name: str
    role: Role
    is_active: bool
