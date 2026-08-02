"""문서 DB 경로 조회→파일 로드→RAG 순서를 고정하는 Document MCP 서비스."""

from mcp_servers.document_tools.document_db import lookup_document_paths
from mcp_servers.document_tools.file_loader import load_document_files
from mcp_servers.document_tools.rag import retrieve
from mcp_servers.document_tools.types import DocumentChunk


async def search_documents(
    query: str,
    top_k: int = 5,
) -> list[DocumentChunk]:
    """Document MCP 공개 도구의 검색 흐름을 수행한다.

    내부 문서 DB에서 관련 파일 경로를 먼저 조회하고, 해당 경로의 파일을 읽은 뒤 RAG
    검색을 수행한다. Document MCP는 문서 DB의 본문을 직접 반환하거나 DB 조회를 건너뛰고
    임의 경로의 파일을 읽지 않는다.
    """
    path_records = await lookup_document_paths(query)
    documents = load_document_files(path_records)
    return await retrieve(query, documents, top_k)
