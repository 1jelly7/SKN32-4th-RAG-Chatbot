from __future__ import annotations

from typing import Any


class LLMClient:
    def __init__(self, api_key: str, model: str) -> None:
        ...

    async def complete(
        self,
        prompt: str,
        context: list[dict[str, Any]],
    ) -> str:
        ...


async def complete(prompt: str, context: list[dict[str, Any]]) -> str:
    ...
