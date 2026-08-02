"""ACL 기반 별도 Document MCP의 검색 결과와 index metadata 타입."""

from __future__ import annotations

from typing import TypedDict


class DocumentChunk(TypedDict):
    """ACL metadata를 포함하는 별도 검색 후보 표현."""

    chunk_id: str
    document_id: str
    title: str
    content: str
    score: float
    updated_at: str
    allowed_roles: list[str]


class IndexMetadata(TypedDict):
    """별도 FAISS index의 version과 chunk 개수."""

    index_version: str
    created_at: str
    chunk_count: int
