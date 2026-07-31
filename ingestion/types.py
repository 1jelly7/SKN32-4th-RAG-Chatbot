from __future__ import annotations

from typing import Any, TypedDict


class RawDocument(TypedDict):
    document_id: str
    path: str
    title: str
    content: str
    metadata: dict[str, Any]


class DocumentChunk(TypedDict):
    chunk_id: str
    document_id: str
    content: str
    metadata: dict[str, Any]


class IndexBuildResult(TypedDict):
    index_path: str
    metadata_path: str
    index_version: str
    chunk_count: int
