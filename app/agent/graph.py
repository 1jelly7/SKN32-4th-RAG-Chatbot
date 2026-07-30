from __future__ import annotations

from typing import Literal

from app.agent.state import GraphState

GraphTransition = Literal["end", "router", "document", "database", "answer"]


def after_cache(state: GraphState) -> GraphTransition:
    """캐시 조회 뒤의 다음 노드를 결정한다.

    ``cached``가 참이면 이미 answer/sources가 복원된 상태이므로 즉시 종료한다.
    캐시 미스면 라우터로 넘긴다. 이 함수는 상태를 변경하거나 MCP/LLM을 호출하지
    않아야 하며, 누락된 ``cached``는 보수적으로 미스로 취급한다.
    """
    ...


def after_router(state: GraphState) -> GraphTransition:
    """확정된 route에 맞는 검색 노드(또는 answer)를 반환한다.

    GENERAL은 검색 없이 answer로, DOCUMENT/DATABASE는 각각 해당 retrieval로,
    BOTH는 두 근거를 모두 수집하는 경로로 보낸다. 허용되지 않거나 누락된 route는
    안전하게 종료/오류 처리하여 근거 없는 답변 생성으로 진행하지 않도록 한다.
    """
    ...


def build_graph() -> object:
    """명세의 StateGraph를 조립하고 컴파일된 실행 객체를 반환한다.

    시작점은 cache_lookup이며, cache hit은 END로, miss는 router로 연결한다. 검색
    결과는 evidence_eval을 거쳐 answer_synthesis와 cache_write로 이어져야 한다.
    BOTH 경로에서는 document/database 결과를 같은 상태에 축적한 뒤에만 평가 노드로
    합류시켜 한쪽 결과가 다른 쪽을 덮어쓰지 않게 한다.
    """
    ...
