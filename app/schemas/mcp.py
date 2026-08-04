"""Host가 MCP Tool 응답을 신뢰하기 전에 검증하는 envelope 모델.

문서·구매·판매 Tool의 공통 success/error 형태를 고정한다. 외부 payload는 이 경계를
통과한 뒤에만 agent evidence로 정규화된다.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ToolName = Literal["search_documents", "resolve_document_download", "query_purchase", "query_sales"]
MCPDomain = Literal["document", "purchase", "sales", "both"]
MCPErrorCode = Literal[
    "FORBIDDEN",
    "INVALID_INPUT",
    "NO_RESULT",
    "QUERY_ERROR",
    "EVIDENCE_INSUFFICIENT",
    "INTERNAL_ERROR",
]


class ToolSuccessEnvelope(BaseModel):
    """MCP Tool의 성공 응답을 경계에서 검증하는 모델이다."""

    status: Literal["success"]
    domain: MCPDomain
    message: None = None
    data: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolErrorEnvelope(BaseModel):
    """MCP Tool의 실패 응답을 경계에서 검증하는 모델이다."""

    status: Literal["error"]
    domain: MCPDomain
    message: str
    error_code: MCPErrorCode
    data: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    """문서 Tool data 항목의 사용자 노출 가능 필드다."""

    content: str
    score: float


class DocumentSource(BaseModel):
    """문서 Tool source 항목에서 내부 경로를 제외한 식별자다."""

    document_id: str
    title: str
    file_name: str | None = None
    page: int | None = None
