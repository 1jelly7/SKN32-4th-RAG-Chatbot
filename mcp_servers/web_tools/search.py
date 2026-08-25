"""실시간 정보가 필요한 질문(FRESHNESS_SENSITIVE)에 웹 검색으로 근거를 보충한다.

document/database 도구와 달리 권한 검사가 필요 없는 공개 정보라, MCP envelope
전체(app/schemas/mcp.py의 ToolName/MCPDomain, InProcessMCPPort 분기, 권한 정책
등록)를 타지 않고 app/agent/nodes.py의 answer_synthesis()가 직접 호출한다
(docs/team_share/08_mcp_tool_addition_pattern.md의 체크리스트는 DB/외부
서비스처럼 권한이 필요한 도메인 기준이라 여기엔 그대로 적용하지 않았다).
"""

from __future__ import annotations

from app.core.config import get_settings

_client = None  # AsyncTavilyClient, 지연 생성 후 프로세스 생애주기 동안 재사용


def _get_client():
    """검증된 API key로 AsyncTavilyClient를 지연 생성해 반환한다."""
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.tavily_api_key:
            raise RuntimeError(
                "TAVILY_API_KEY가 설정되지 않아 웹 검색을 쓸 수 없습니다."
            )
        from tavily import AsyncTavilyClient

        _client = AsyncTavilyClient(api_key=settings.tavily_api_key)
    return _client


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """웹 검색 결과를 evidence 표준 형태로 변환해 반환한다.

    반드시 "content" 키를 써야 한다 - app/agent/llm.py의 sanitize_evidence()가
    이 키 이름만 보고 프롬프트 인젝션 필터(_strip_injection_markers)를 자동
    적용하기 때문이다(document/database evidence와 동일한 계약, 별도 필터링
    코드를 여기 새로 만들 필요 없음).
    """
    client = _get_client()
    response = await client.search(query, max_results=max_results, search_depth="basic")
    return [
        {
            "type": "web",
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
            "score": item.get("score"),
        }
        for item in response.get("results", [])
    ]
