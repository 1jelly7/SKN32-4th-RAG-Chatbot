"""Document MCP가 경로 조회를 우회해 임의 파일을 읽지 않는 순서 계약."""

import asyncio

import mcp_servers.document_tools.search as search_module


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
