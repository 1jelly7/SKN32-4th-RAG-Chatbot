"""FastAPI와 LangGraph 사이의 유일한 answer-cache 진입점.

lookup은 그래프 실행 전에, write는 그래프 완료 후에만 호출된다. Router, MCP client,
evidence 평가 노드는 이 저장소를 직접 읽거나 쓰지 않는다.
"""

from __future__ import annotations

from app.agent.state import GraphState
from app.cache.key import make_cache_key
from app.cache.policy import get_cache_ttl, should_cache
from app.cache.repository import CacheRepository, CacheValue, cache


def lookup_cached_answer(
    state: GraphState, repository: CacheRepository = cache
) -> CacheValue | None:
    """LangGraph 실행 전에 캐시를 조회하고 hit 여부를 상태에 기록한다.

    반환값이 있으면 호출자는 즉시 응답해 Graph·LLM·MCP를 호출하지 않아야 한다.
    """
    cache_key = make_cache_key(state)
    state["cache_key"] = cache_key
    cached_value = repository.get(cache_key)
    state["cached"] = cached_value is not None
    return cached_value


def write_answer_cache(state: GraphState, repository: CacheRepository = cache) -> bool:
    """LangGraph 완료 후 재사용 가능한 최종 답변만 캐시에 저장한다.

    오류, 불충분·상충 근거, 이전 cache hit는 저장하지 않는다. 실제 재인덱싱·ETL
    freshness 공급과 분산 무효화는 아직 이 저장 경계에 연결돼 있지 않다.
    """
    route = state.get("route")
    if route is None or not should_cache(state):
        return False

    cache_key = state.get("cache_key") or make_cache_key(state)
    cache_value: CacheValue = {
        "answer": state.get("answer", ""),
        "sources": state.get("sources", []),
        "tables": state.get("tables", []),
        "route": route,
    }
    if state.get("evidence_status") is not None:
        cache_value["evidence_status"] = state["evidence_status"]
    repository.set(cache_key, cache_value, get_cache_ttl(route))
    state["cache_key"] = cache_key
    return True
