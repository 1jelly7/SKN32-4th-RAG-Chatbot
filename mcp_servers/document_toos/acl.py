from __future__ import annotations

from typing import Any

from app.core.security import UserContext


def filter_allowed(
    documents: list[dict[str, Any]],
    user_context: UserContext,
) -> list[dict[str, Any]]:
    ...
