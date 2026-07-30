from __future__ import annotations

from typing import Any, TypedDict


class UserContext(TypedDict):
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
    ...


def validate_user_context(context: dict[str, Any]) -> UserContext:
    ...
