"""문서 DB 경로 조회→FAISS 인덱스 검색 순서를 고정하는 Document MCP 서비스."""

import logging

import pymysql

from mcp_servers.document_tools.document_db import lookup_document_paths
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

    내부 문서 DB에서 관련 파일 경로를 먼저 조회한 뒤, scripts/ingest_documents.py가
    미리 만들어둔 정식 FAISS 인덱스에서 검색한다. retrieve()는 document_id로만
    후보를 좁히고 실제 본문은 인덱스에서 가져오므로(DCC-008), 질문마다 디스크에서
    파일을 다시 읽지 않는다 — 이전에는 매 질문마다 load_document_files()로 파일을
    재로딩했는데, retrieve()가 어차피 document_id만 쓰고 content는 버려서 불필요한
    디스크 I/O이자 불필요한 실패 지점(파일 경로가 깨지면 검색 전체가 죽음)이었다.
    """
    try:
        path_records = await lookup_document_paths(query)
    except pymysql.MySQLError as exc:
        error_number = (
            exc.args[0] if exc.args and isinstance(exc.args[0], int) else None
        )
        logger.warning(
            "document_path_lookup_failed error_type=%s error_number=%s",
            type(exc).__name__,
            error_number,
            extra={"event": "document_path_lookup_failed"},
        )
        raise DocumentSearchUnavailableError(
            "Document path lookup is unavailable."
        ) from exc
    return await retrieve(query, path_records, top_k)
