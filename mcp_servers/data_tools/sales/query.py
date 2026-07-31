from __future__ import annotations

from typing import Any

from app.core.security import UserContext


async def query_sales(question: str, user_context: UserContext) -> list[dict[str, Any]]:
    """판매 질문만 Text2SQL → SQL Guard → read-only 조회로 처리한다."""
    ...
