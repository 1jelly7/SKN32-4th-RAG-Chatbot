from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Source(BaseModel):
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
    question: str = Field(min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    tables: list[TableData] = Field(default_factory=list)
    cached: bool
    route: str | None = None
    request_id: str | None = None
