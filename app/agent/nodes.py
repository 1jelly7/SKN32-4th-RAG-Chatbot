from app.cache.repository import cache
from app.cache.key import make_cache_key
from app.mcp.client import document_search, data_query
from app.agent.llm import complete

def route_question(question: str) -> str:
    q = question.lower()
    if any(x in q for x in ["매출", "건수", "고객", "이번 달", "지난달"]): return "DATABASE"
    if any(x in q for x in ["정책", "규정", "매뉴얼", "문서"]): return "DOCUMENT"
    return "GENERAL"

async def cache_lookup(state):
    item = cache.get(make_cache_key(state))
    return {"answer": item["answer"], "sources": item.get("sources", []), "cached": True} if item else {"cached": False}
async def router(state): return {"route": route_question(state["question"])}
async def document_retrieval(state): return {"evidence": await document_search(state["question"], state.get("user_context", {}))}
async def database_retrieval(state): return {"evidence": await data_query(state["question"], state.get("user_context", {}))}
async def evidence_eval(state): return {"sources": state.get("evidence", [])}
async def answer_synthesis(state):
    if state.get("cached"): return {}
    return {"answer": await complete(state["question"])}
async def cache_write(state):
    if state.get("answer") and not state.get("cached"): cache.set(make_cache_key(state), {"answer": state["answer"], "sources": state.get("sources", [])})
    return {}
