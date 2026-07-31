from app.core.security import UserContext
from mcp_servers.document.types import DocumentChunk


async def search_documents(
    query: str,
    user_context: UserContext,
    top_k: int = 5,
) -> list[DocumentChunk]:
    ...
