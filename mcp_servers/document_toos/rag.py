from mcp_servers.document.types import DocumentChunk


async def retrieve(query: str, top_k: int) -> list[DocumentChunk]:
    ...
