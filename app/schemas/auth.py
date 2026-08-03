"""인증 API의 비밀정보 없는 요청과 응답 계약이다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class UserProfile(BaseModel):
    user_id: int
    username: str
    display_name: str
    role: Literal["admin", "hr", "finance"]
    allowed_databases: list[str]


class LoginResponse(BaseModel):
    user: UserProfile
