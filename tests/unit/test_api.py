from pathlib import Path

from fastapi.testclient import TestClient

from app.agent.llm import LLMClient
from app.cache.repository import MemoryCache
from app.core.dependencies import AppDependencies
from app.main import create_app
from app.mcp.client import MCPClient


class FakeLLMClient(LLMClient):
    def __init__(self) -> None:
        pass


class FakeMCPClient(MCPClient):
    def __init__(self) -> None:
        pass


def test_health_uses_injected_dependencies_without_file_logging(tmp_path: Path) -> None:
    configured = False
    log_path = tmp_path / "app.log.txt"

    def configure_test_logging() -> None:
        nonlocal configured
        configured = True

    fake_llm = FakeLLMClient()
    fake_mcp = FakeMCPClient()
    fake_cache = MemoryCache()
    dependencies = AppDependencies(
        llm=fake_llm,
        mcp=fake_mcp,
        cache=fake_cache,
        configure_logging=configure_test_logging,
    )
    application = create_app(dependencies)

    with TestClient(application) as client:
        assert client.get("/api/health").status_code == 200

    assert configured is True
    assert application.state.dependencies is dependencies
    assert application.state.dependencies.llm is fake_llm
    assert application.state.dependencies.mcp is fake_mcp
    assert application.state.dependencies.cache is fake_cache
    assert log_path.exists() is False
