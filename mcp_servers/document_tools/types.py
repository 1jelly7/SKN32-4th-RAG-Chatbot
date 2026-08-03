"""Document MCP 내부 경로 레코드와 공개 가능한 검색 결과 타입."""

from __future__ import annotations

from typing import TypedDict


class DocumentPathRecord(TypedDict):
    """문서 DB가 본문 대신 반환하는 내부 파일 위치 metadata."""

    document_id: str
    title: str
    file_path: str
    updated_at: str


class DocumentChunk(TypedDict):
    """내부 file_path를 제거한 문서 검색 결과."""

    chunk_id: str
    document_id: str
    title: str
    content: str
    score: float
    updated_at: str
    page: int | None


class IndexMetadata(TypedDict):
    """인덱스·metadata 일관성과 cache freshness를 식별한다."""

    index_version: str
    created_at: str
    chunk_count: int
