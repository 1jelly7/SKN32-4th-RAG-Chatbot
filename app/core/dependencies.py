from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.agent.llm import AsyncLLMPort
from app.cache.repository import CacheRepository, MemoryCache
from app.logging import configure_logging
from app.mcp.client import MCPClient


@dataclass
class AppDependencies:
    """앱 수명주기 동안 공유할 외부 경계와 테스트 대역을 묶는다."""

    llm: AsyncLLMPort | None = None
    mcp: MCPClient | None = None
    cache: CacheRepository = field(default_factory=MemoryCache)
    configure_logging: Callable[[], None] = configure_logging
