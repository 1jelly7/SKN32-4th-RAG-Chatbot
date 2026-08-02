"""앱 factory에 외부 경계와 테스트 대역을 주입하는 composition 모델."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.agent.llm import AsyncLLMPort
from app.cache.repository import CacheRepository, MemoryCache
from app.logging import configure_logging
from app.mcp.client import InProcessMCPPort, MCPClient


@dataclass
class AppDependencies:
    """앱 수명주기 동안 공유할 외부 경계와 테스트 대역을 묶는다.

    단위·mock 통합 테스트는 이 객체를 통해 실제 OpenAI, MCP, Redis를 호출하지 않는
    결정적 fake를 주입한다. ``None`` provider는 운영 연결이 구성됐다는 의미가 아니다.
    """

    llm: AsyncLLMPort | None = None
    mcp: MCPClient | None = field(default_factory=lambda: MCPClient(InProcessMCPPort()))
    cache: CacheRepository = field(default_factory=MemoryCache)
    configure_logging: Callable[[], None] = configure_logging
