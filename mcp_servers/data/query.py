from __future__ import annotations

from typing import Any

from app.core.security import UserContext


async def query_business_data(
    question: str,
    user_context: UserContext,
) -> list[dict[str, Any]]:
    ...
