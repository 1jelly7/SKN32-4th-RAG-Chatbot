from __future__ import annotations

from typing import Any

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
    user_context: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    cached: bool
    route: str | None = None
    request_id: str | None = None
