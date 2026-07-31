from __future__ import annotations

from pydantic import BaseModel, Field


class Source(BaseModel):
    id: str
    title: str
    source_type: str
    document_id: str | None = None
    score: float | None = None
    updated_at: str | None = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    cached: bool
    route: str | None = None
    request_id: str | None = None
