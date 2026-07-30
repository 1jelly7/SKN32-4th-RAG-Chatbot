from __future__ import annotations

from typing import Any, Literal, TypedDict

Route = Literal["GENERAL", "DOCUMENT", "DATABASE", "BOTH"]
EvidenceStatus = Literal[
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT",
    "CONTRADICTED",
]


class GraphState(TypedDict, total=False):
    question: str
    session_id: str | None
    user_context: dict[str, Any]
    request_id: str
    route: Route
    cache_key: str
    cached: bool
    document_evidence: list[dict[str, Any]]
    database_evidence: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    evidence_status: EvidenceStatus
    sources: list[dict[str, Any]]
    answer: str
