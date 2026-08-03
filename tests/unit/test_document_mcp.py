"""Document MCP가 경로 조회를 우회해 임의 파일을 읽지 않는 순서 계약."""

import asyncio
from pathlib import Path
from typing import Any

import pymysql
import pytest

import mcp_servers.document_tools.search as search_module
import mcp_servers.document_tools.file_loader as file_loader_module
from mcp_servers.document_tools.document_db import DocumentPathRepository
from tests.auth_helpers import TEST_ADMIN_CONTEXT


def test_document_path_lookup_does_not_exclude_semantically_related_titles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """질문의 일반어가 일부 제목과 일치해도 활성 문서 전체를 허용 목록에 둔다."""
    executed_sql: list[str] = []
    rows = [
        {
            "document_id": "doc-work-rule",
            "title": "취업규칙",
            "file_path": "documents/work-rule.pdf",
            "updated_at": "2026-08-01",
        },
        {
            "document_id": "doc-accounting",
            "title": "회계규정",
            "file_path": "documents/accounting.pdf",
            "updated_at": "2026-08-01",
        },
    ]

    class FakeCursor:
        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def execute(self, sql: str) -> None:
            executed_sql.append(sql)

        def fetchall(self) -> list[dict[str, object]]:
            return rows

    class FakeConnection:
        def cursor(self) -> FakeCursor:
            return FakeCursor()

        def close(self) -> None:
            return None

    monkeypatch.setattr("mcp_servers.document_tools.document_db.pymysql.connect", lambda **_: FakeConnection())
    repository = DocumentPathRepository("host", "user", "password", "document_db")

    result = repository._find_paths_sync("겸직 규정")

    assert [record["document_id"] for record in result] == ["doc-work-rule", "doc-accounting"]
    assert len(executed_sql) == 1
    assert "LIKE" not in executed_sql[0]


def test_document_search_resolves_database_paths_before_loading(monkeypatch) -> None:
    """문서 DB 경로 조회→해당 파일 로드→RAG 순서를 회귀로 고정한다."""
    calls: list[str] = []
    path_record = {
        "document_id": "doc-1",
        "title": "업무 문서",
        "file_path": "documents/manual.md",
        "updated_at": "2026-07-31T00:00:00+09:00",
    }
    raw_document = {
        "document_id": "doc-1",
        "path": "documents/manual.md",
        "title": "업무 문서",
        "content": "본문",
        "metadata": {"updated_at": path_record["updated_at"]},
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

    def fake_load(records):
        assert calls == ["path_lookup"]
        assert records == [path_record]
        calls.append("file_load")
        return [raw_document]

    async def fake_retrieve(query, documents, top_k):
        assert calls == ["path_lookup", "file_load"]
        assert documents == [raw_document]
        calls.append("rag")
        return [chunk]

    monkeypatch.setattr(search_module, "lookup_document_paths", fake_lookup)
    monkeypatch.setattr(search_module, "load_document_files", fake_load)
    monkeypatch.setattr(search_module, "retrieve", fake_retrieve)

    result = asyncio.run(search_module.search_documents("업무 문서", top_k=3))
    assert result == [chunk]
    assert calls == ["path_lookup", "file_load", "rag"]


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


def test_document_file_cache_uses_path_and_updated_at(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """같은 버전은 재파싱하지 않고 DB 갱신 시각이 바뀌면 다시 읽는다."""
    path = tmp_path / "policy.txt"
    path.write_text("정책 본문", encoding="utf-8")
    calls = 0

    def fake_load_text(file_path: Path) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {
            "document_id": "original",
            "path": str(file_path),
            "title": "original",
            "content": "정책 본문",
            "metadata": {},
        }

    monkeypatch.setattr(file_loader_module, "load_text", fake_load_text)
    file_loader_module.invalidate_document_cache()
    record = {
        "document_id": "doc-1",
        "title": "정책",
        "file_path": str(path),
        "updated_at": "2026-08-01T00:00:00",
    }

    first = file_loader_module.load_document_files([record])
    first[0]["content"] = "호출자 변경"
    second = file_loader_module.load_document_files([record])
    updated = file_loader_module.load_document_files(
        [{**record, "updated_at": "2026-08-02T00:00:00"}]
    )

    assert calls == 2
    assert second[0]["content"] == "정책 본문"
    assert updated[0]["metadata"]["updated_at"] == "2026-08-02T00:00:00"
