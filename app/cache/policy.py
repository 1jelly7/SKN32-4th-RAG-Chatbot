from app.agent.state import GraphState, Route


def get_cache_ttl(route: Route) -> int:
    ...


def should_cache(state: GraphState) -> bool:
    ...
