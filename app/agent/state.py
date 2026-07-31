from __future__ import annotations

from typing import Any, Literal, TypedDict

Route = Literal["GENERAL", "DOCUMENT", "DATABASE", "BOTH"]
DataDomain = Literal["finance", "sales"]
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
    data_domain: DataDomain
    cache_key: str
    cached: bool
    conversation_context_hash: str
    document_index_version: str
    database_freshness_bucket: str
    prompt_version: str
    model_id: str
    document_evidence: list[dict[str, Any]]
    database_evidence: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    evidence_status: EvidenceStatus
    sources: list[dict[str, Any]]
    answer: str
