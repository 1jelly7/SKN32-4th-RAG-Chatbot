from __future__ import annotations

from app.agent.state import GraphState
from app.cache.key import make_cache_key
from app.cache.policy import get_cache_ttl, should_cache
from app.cache.repository import CacheValue, cache


def lookup_cached_answer(state: GraphState) -> CacheValue | None:
    """LangGraph 실행 전에 캐시를 조회하고 hit 여부를 상태에 기록한다."""
    cache_key = make_cache_key(state)
    state["cache_key"] = cache_key
    cached_value = cache.get(cache_key)
    state["cached"] = cached_value is not None
    return cached_value


def write_answer_cache(state: GraphState) -> bool:
    """LangGraph 완료 후 재사용 가능한 최종 답변만 캐시에 저장한다."""
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
    cache.set(cache_key, cache_value, get_cache_ttl(route))
    state["cache_key"] = cache_key
    return True
