"""캐시 miss 요청만 실행하는 LangGraph 조립 모듈.

``BOTH``는 document→database 순서로 두 근거를 수집한 뒤 단일 evidence 평가 노드에
합류한다. 캐시 조회·저장은 의도적으로 그래프 밖에 있다.
"""

from __future__ import annotations

from functools import partial
from typing import Literal

from langgraph.graph import END, StateGraph

from app.agent.evidence_eval import evidence_eval
from app.agent.llm import AsyncLLMPort
from app.agent.nodes import answer_synthesis, database_retrieval, document_retrieval, router
from app.agent.state import GraphState
from app.mcp.client import MCPClient

GraphTransition = Literal["end", "router", "document", "database", "answer"]


def after_router(state: GraphState) -> str:
    """확정된 route에 맞는 검색 노드(또는 answer)를 반환한다.

    GENERAL은 검색 없이 answer로, DOCUMENT/DATABASE는 각각 해당 retrieval로,
    BOTH는 두 근거를 모두 수집하는 경로(document -> database 순으로 이어붙임)로
    보낸다. 허용되지 않거나 누락된 route는 안전하게 answer로 보내 근거 없는 값을
    지어내지 않고 "근거 없음" 응답으로 귀결되게 한다.
    """
    route = state.get("route")
    if route == "DOCUMENT":
        return "document"
    if route == "DATABASE":
        return "database"
    if route == "BOTH":
        return "document"  # BOTH는 document -> database 순으로 이어서 둘 다 수집합니다.
    # GENERAL이거나 알 수 없는 값이면 검색 없이 바로 답변 생성으로 갑니다.
    return "answer"


def after_document(state: GraphState) -> str:
    """BOTH 경로면 database_retrieval로 이어가고, DOCUMENT 단독이면 평가로 간다."""
    if state.get("route") == "BOTH":
        return "database"
    return "evidence"


def build_graph(
    mcp_client: MCPClient | None = None,
    llm: AsyncLLMPort | None = None,
) -> object:
    """명세의 StateGraph를 조립하고 컴파일된 실행 객체를 반환한다.

    캐시 miss 상태만 이 그래프에 진입하므로 시작점은 router다. 검색 결과는
    evidence_eval을 거쳐 answer_synthesis로 이어진다. 최종 캐시 저장은 그래프 밖의
    app.cache.service가 담당한다. BOTH 경로에서는 document 노드를 거친 뒤 database
    노드로 이어가, 같은 state 딕셔너리에 두 근거를 순서대로 누적한 다음에만 평가
    노드로 합류시켜 한쪽 결과가 다른 쪽을 덮어쓰지 않게 한다.
    """
    graph = StateGraph(GraphState)

    graph.add_node("router", router)
    graph.add_node("document", partial(document_retrieval, mcp_client=mcp_client))
    graph.add_node("database", partial(database_retrieval, mcp_client=mcp_client))
    graph.add_node("evidence", evidence_eval)
    graph.add_node("answer", partial(answer_synthesis, llm=llm))

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        after_router,
        {"document": "document", "database": "database", "answer": "answer"},
    )
    graph.add_conditional_edges(
        "document",
        after_document,
        {"database": "database", "evidence": "evidence"},
    )
    graph.add_edge("database", "evidence")
    graph.add_edge("evidence", "answer")
    graph.add_edge("answer", END)

    return graph.compile()


_compiled_graph = None


def get_graph(
    mcp_client: MCPClient | None = None,
    llm: AsyncLLMPort | None = None,
) -> object:
    """컴파일된 그래프를 매 요청마다 새로 빌드하지 않도록 캐싱해서 반환한다."""
    if mcp_client is not None or llm is not None:
        return build_graph(mcp_client, llm)
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
