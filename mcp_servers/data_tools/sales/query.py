from __future__ import annotations

from typing import Any


async def query_sales(question: str) -> list[dict[str, Any]]:
    """판매 질문을 Text2SQL → read-only 조회 순서로 처리한다."""
    ...
