"""Document MCP가 경로 조회를 우회해 임의 파일을 읽지 않는 순서 계약."""

import asyncio

import pymysql
import pytest

import mcp_servers.document_tools.search as search_module
from tests.auth_helpers import TEST_ADMIN_CONTEXT


def test_document_search_resolves_database_paths_before_loading(monkeypatch) -> None:
    """문서 DB 경로 조회→RAG 순서와 조회 결과 범위를 회귀로 고정한다."""
    calls: list[str] = []
    path_record = {
        "document_id": "doc-1",
        "title": "업무 문서",
        "file_path": "documents/manual.md",
        "updated_at": "2026-07-31T00:00:00+09:00",
    }
    chunk = {
        "chunk_id": "chunk-1",
        "document_id": "doc-1",
        "title": "업무 문서",
        "content": "본문",
        "score": 1.0,
        "updated_at": path_record["updated_at"],
    }

    async def fake_lookup(query):
        calls.append("path_lookup")
        return [path_record]

    async def fake_retrieve(query, documents, top_k):
        # RAG는 반드시 경로 조회 뒤에 실행되고, 조회 결과 밖의 문서는 볼 수 없어야 한다.
        assert calls == ["path_lookup"]
        assert documents == [path_record]
        assert {d["document_id"] for d in documents} == {"doc-1"}
        calls.append("rag")
        return [chunk]

    monkeypatch.setattr(search_module, "lookup_document_paths", fake_lookup)
    monkeypatch.setattr(search_module, "retrieve", fake_retrieve)

    result = asyncio.run(search_module.search_documents("업무 문서", top_k=3))
    assert result == [chunk]
    assert calls == ["path_lookup", "rag"]


def test_document_database_error_is_classified_as_search_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DB authentication or connection failures must not be reported as RAG internals."""
    async def failed_lookup(_: str) -> list[dict[str, str]]:
        raise pymysql.err.OperationalError(1045, "credential detail must not escape")

    monkeypatch.setattr(search_module, "lookup_document_paths", failed_lookup)

    with pytest.raises(search_module.DocumentSearchUnavailableError):
        asyncio.run(search_module.search_documents("policy", top_k=3))


def test_in_process_mcp_maps_document_database_error_to_query_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The host must distinguish an unavailable document backend from an internal error."""
    from app.mcp.client import InProcessMCPPort, MCPClient, MCPQueryError

    async def unavailable_search(_: str, __: int) -> list[dict[str, str]]:
        raise search_module.DocumentSearchUnavailableError("private backend detail")

    monkeypatch.setattr(search_module, "search_documents", unavailable_search)

    with pytest.raises(MCPQueryError):
        asyncio.run(MCPClient(InProcessMCPPort()).document_search("policy", top_k=3, user_context=TEST_ADMIN_CONTEXT))
