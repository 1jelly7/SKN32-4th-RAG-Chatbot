from __future__ import annotations

from typing import Any

from app.core.security import UserContext


class MCPClient:
    def __init__(self, document_mcp_url: str, data_mcp_url: str) -> None:
        ...

    async def document_search(
        self,
        query: str,
        user_context: UserContext,
        top_k: int,
    ) -> list[dict[str, Any]]:
        ...

    async def data_query(
        self,
        question: str,
        user_context: UserContext,
    ) -> list[dict[str, Any]]:
        ...


async def document_search(
    query: str,
    user_context: UserContext,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    ...


async def data_query(
    question: str,
    user_context: UserContext,
) -> list[dict[str, Any]]:
    ...
