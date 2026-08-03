"""문서 DB 경로 조회→파일 로드→RAG 순서를 고정하는 Document MCP 서비스."""

import logging

import pymysql

from mcp_servers.document_tools.document_db import lookup_document_paths
from mcp_servers.document_tools.file_loader import load_document_files
from mcp_servers.document_tools.rag import retrieve
from mcp_servers.document_tools.types import DocumentChunk

logger = logging.getLogger(__name__)


class DocumentSearchUnavailableError(RuntimeError):
    """Document-path storage is unavailable, so RAG retrieval cannot proceed."""


async def search_documents(
    query: str,
    top_k: int = 5,
) -> list[DocumentChunk]:
    """Document MCP 공개 도구의 검색 흐름을 수행한다.

    내부 문서 DB에서 관련 파일 경로를 먼저 조회하고, 해당 경로의 파일을 읽은 뒤 RAG
    검색을 수행한다. Document MCP는 문서 DB의 본문을 직접 반환하거나 DB 조회를 건너뛰고
    임의 경로의 파일을 읽지 않는다.
    """
    try:
        path_records = await lookup_document_paths(query)
    except pymysql.MySQLError as exc:
        error_number = exc.args[0] if exc.args and isinstance(exc.args[0], int) else None
        logger.warning(
            "document_path_lookup_failed error_type=%s error_number=%s",
            type(exc).__name__,
            error_number,
            extra={"event": "document_path_lookup_failed"},
        )
        raise DocumentSearchUnavailableError("Document path lookup is unavailable.") from exc
    documents = load_document_files(path_records)
    return await retrieve(query, documents, top_k)
