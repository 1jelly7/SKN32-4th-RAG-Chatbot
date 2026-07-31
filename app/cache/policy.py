from app.agent.state import GraphState, Route


def get_cache_ttl(route: Route) -> int:
    """route별 허용 TTL(초)을 반환한다.

    DATABASE는 데이터 신선도를 위해 짧게(예: 1~5분), 문서 기반은 인덱스 버전을 키에
    포함한 전제에서 더 길게 설정한다. 지원하지 않는 route는 장기 캐시하지 않는 안전한
    기본값 또는 명시적 오류를 사용한다.
    """
    ttl_by_route: dict[Route, int] = {
        "GENERAL": 300,
        "DOCUMENT": 3600,
        "DATABASE": 300,
        "BOTH": 300,
    }
    return ttl_by_route[route]


def should_cache(state: GraphState) -> bool:
    """현재 답변이 재사용 가능한지 판정한다.

    answer와 키가 있고, evidence 상태가 충분하며, 개인별·일회성·오류 응답이 아닌지를
    확인한다. 캐시 hit 응답과 INSUFFICIENT/CONTRADICTED 결과는 다시 저장하지 않는다.
    """
    if state.get("cached") or not state.get("answer") or not state.get("cache_key"):
        return False
    if state.get("route") == "GENERAL":
        return True
    return state.get("evidence_status") == "SUPPORTED"
