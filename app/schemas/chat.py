"""채팅 HTTP 요청·응답의 공개 Pydantic 계약.

내부 evidence를 그대로 노출하지 않고 사용자에게 허용된 출처·표 metadata만 표현한다.
특히 내부 파일 경로와 provider 자격증명은 이 모델의 필드가 아니다.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    """문서 또는 DB 근거를 공개 식별자와 freshness 정보로 표현한다."""

    id: str
    title: str
    source_type: str
    document_id: str | None = None
    score: float | None = None
    page: int | None = None
    updated_at: str | None = None
    table_name: str | None = None
    query_id: str | None = None
    freshness_seconds: float | None = None
    source_version: str | None = None


class TableData(BaseModel):
    """DB 조회 결과를 표/차트로 그릴 수 있는 형태입니다."""

    domain: str  # "purchase", "sales" 또는 "both"
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    # 프론트엔드가 차트를 그릴 때 참고할 힌트입니다. (숫자 컬럼이 있을 때만 채워짐)
    chartable: bool = False
    label_column: str | None = None
    value_column: str | None = None
    table_name: str | None = None
    query_id: str | None = None
    freshness_seconds: float | None = None
    source_version: str | None = None


class ChatRequest(BaseModel):
    """비어 있지 않은 질문과 선택적 대화 세션 식별자를 받는다."""

    question: str = Field(min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    """최종 답변과 안전하게 직렬화된 출처·표·캐시 상태를 반환한다."""

    answer: str
    sources: list[Source] = Field(default_factory=list)
    tables: list[TableData] = Field(default_factory=list)
    cached: bool
    route: str | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Tool 오류를 비밀값 없이 API 경계에서 표현하는 응답이다."""

    detail: str
    error_code: Literal[
        "INVALID_INPUT",
        "NO_RESULT",
        "QUERY_ERROR",
        "EVIDENCE_INSUFFICIENT",
        "INTERNAL_ERROR",
    ]
