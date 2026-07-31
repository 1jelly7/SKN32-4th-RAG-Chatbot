from __future__ import annotations

from typing import TypedDict


class DocumentChunk(TypedDict):
    chunk_id: str
    document_id: str
    title: str
    content: str
    score: float
    updated_at: str
    allowed_roles: list[str]


class IndexMetadata(TypedDict):
    index_version: str
    created_at: str
    chunk_count: int
