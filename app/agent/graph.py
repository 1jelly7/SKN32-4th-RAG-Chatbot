from langgraph.graph import StateGraph, END
from app.agent.state import GraphState
from app.agent import nodes

def _after_cache(state): return "end" if state.get("cached") else "router"
def _after_router(state): return {"DOCUMENT":"document", "DATABASE":"database", "BOTH":"document"}.get(state.get("route"), "answer")
def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("cache", nodes.cache_lookup); graph.add_node("router", nodes.router)
    graph.add_node("document", nodes.document_retrieval); graph.add_node("database", nodes.database_retrieval)
    graph.add_node("evaluate", nodes.evidence_eval); graph.add_node("answer", nodes.answer_synthesis); graph.add_node("write", nodes.cache_write)
    graph.set_entry_point("cache"); graph.add_conditional_edges("cache", _after_cache, {"end":END,"router":"router"})
    graph.add_conditional_edges("router", _after_router, {"document":"document","database":"database","answer":"answer"})
    graph.add_edge("document", "evaluate"); graph.add_edge("database", "evaluate"); graph.add_edge("evaluate", "answer"); graph.add_edge("answer", "write"); graph.add_edge("write", END)
    return graph.compile()
