"""mcp_servers/web_tools/search.py의 evidence 변환 계약을 검증한다.

실제 Tavily 네트워크 호출은 절대 하지 않는다 - AsyncTavilyClient.search()를
monkeypatch로 대체해 응답 형태만 고정하고, search_web()이 그걸 프로젝트
표준 evidence 형태({"type": "web", "content": ...})로 정확히 바꾸는지만 본다.
"""

from __future__ import annotations

import pytest

from mcp_servers.web_tools import search as search_module


class _FakeTavilyClient:
    def __init__(self, results: list[dict]) -> None:
        self._results = results

    async def search(
        self, query: str, max_results: int = 5, search_depth: str = "basic"
    ) -> dict:
        return {"results": self._results}


@pytest.fixture(autouse=True)
def _reset_client_cache():
    """모듈 전역 _client 캐시가 테스트 간 오염되지 않게 초기화한다."""
    search_module._client = None
    yield
    search_module._client = None


@pytest.mark.asyncio
async def test_search_web_converts_tavily_results_to_standard_evidence(
    monkeypatch,
) -> None:
    fake_results = [
        {
            "title": "제목1",
            "url": "https://a.example.com",
            "content": "본문1",
            "score": 0.8,
        },
        {
            "title": "제목2",
            "url": "https://b.example.com",
            "content": "본문2",
            "score": 0.6,
        },
    ]
    search_module._client = _FakeTavilyClient(fake_results)

    evidence = await search_module.search_web("아무 질문")

    assert evidence == [
        {
            "type": "web",
            "title": "제목1",
            "url": "https://a.example.com",
            "content": "본문1",
            "score": 0.8,
        },
        {
            "type": "web",
            "title": "제목2",
            "url": "https://b.example.com",
            "content": "본문2",
            "score": 0.6,
        },
    ]


@pytest.mark.asyncio
async def test_search_web_returns_empty_list_when_no_results() -> None:
    search_module._client = _FakeTavilyClient([])

    evidence = await search_module.search_web("결과 없는 질문")

    assert evidence == []


def test_get_client_raises_clear_error_without_api_key(monkeypatch) -> None:
    """TAVILY_API_KEY가 없으면, 네트워크를 타기 전에 명확한 에러로 즉시 실패한다."""
    from app.core import config

    monkeypatch.setattr(
        config, "get_settings", lambda: type("S", (), {"tavily_api_key": ""})()
    )
    monkeypatch.setattr(search_module, "get_settings", config.get_settings)

    with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
        search_module._get_client()
