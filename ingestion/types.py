"""문서 loader, chunker, index builder 사이의 provenance 타입 계약."""

from __future__ import annotations

from typing import Any, TypedDict


class RawDocument(TypedDict):
    """검증된 문서 경로에서 읽은 원문과 로더 metadata."""

    document_id: str
    path: str
    title: str
    content: str
    metadata: dict[str, Any]


class DocumentChunk(TypedDict):
    """FAISS vector와 동일 순서로 저장되는 검색 단위."""

    chunk_id: str
    document_id: str
    content: str
    metadata: dict[str, Any]


class IndexBuildResult(TypedDict):
    """원자적 인덱스 빌드가 생성한 파일과 freshness version."""

    index_path: str
    metadata_path: str
    index_version: str
    chunk_count: int
