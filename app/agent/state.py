from typing import TypedDict
class GraphState(TypedDict, total=False):
    question: str
    session_id: str
    user_context: dict
    route: str
    evidence: list[dict]
    sources: list[dict]
    answer: str
    cached: bool
