"""Host가 MCP Tool 응답을 신뢰하기 전에 검증하는 envelope 모델.

문서·구매·판매 Tool의 공통 success/error 형태를 고정한다. 외부 payload는 이 경계를
통과한 뒤에만 agent evidence로 정규화된다.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ToolName = Literal[
    "search_documents", "resolve_document_download", "query_purchase", "query_sales"
]
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
    """MCP Tool의 성공 응답을 경계에서 검증하는 모델이다.

    data의 원소 형태는 domain마다 다르다: document는 DocumentChunk({content, score}),
    purchase/sales는 복합질문 지원을 위해 DatabaseQueryBlock({label, generated_sql,
    rows, row_count, metadata})이다. 서로 다른 컬럼 구조의 표 여러 개를 하나의 평면
    rows 리스트에 담을 수 없어서, purchase/sales는 data 자체를 "쿼리 블록의 리스트"로
    쓴다(app/mcp/client.py의 _database_evidence가 domain별로 다르게 해석한다).
    """

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


# 추가: 복합질문(예: "올해 매출과 매출 최고 기업")에서 purchase/sales Tool이
# ToolSuccessEnvelope.data의 원소로 담는 하위 SELECT 결과 1개. 항목마다 컬럼 구조가
# 다를 수 있어(합계 1건 vs 순위 목록) rows를 평면 리스트로 합치지 않고 블록 단위로
# 나눠 보존한다.
class DatabaseQueryBlock(BaseModel):
    """purchase/sales Tool의 하위 SELECT 결과 1개를 경계에서 검증하는 모델이다."""

    label: str = ""
    generated_sql: str
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentSource(BaseModel):
    """문서 Tool source 항목에서 내부 경로를 제외한 식별자다."""

    document_id: str
    title: str
    file_name: str | None = None
    page: int | None = None
