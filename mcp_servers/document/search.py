from mcp_servers.document.rag import retrieve
from mcp_servers.document.acl import filter_allowed
async def search_documents(query: str, user_context: dict, top_k: int = 5) -> list[dict]:
    return filter_allowed(await retrieve(query, top_k), user_context)
