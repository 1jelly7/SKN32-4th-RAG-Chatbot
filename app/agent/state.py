from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict

Route = Literal["GENERAL", "DOCUMENT", "DATABASE", "BOTH"]
DataDomain = Literal["purchase", "sales", "both"]
EvidenceStatus = Literal[
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT",
    "CONTRADICTED",
]


@dataclass(frozen=True)
class EvidencePolicy:
    """근거 품질 평가에 주입하는 결정적 정책값이다."""

    min_relevance: float = 0.5
    min_confidence: float = 0.5
    required_metadata_keys: tuple[str, ...] = ()
    max_freshness_seconds: float | None = None


class GraphState(TypedDict, total=False):
    question: str
    session_id: str | None
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
    evidence_policy: EvidencePolicy
    _errors: list[str]
    evidence: list[dict[str, Any]]
    evidence_status: EvidenceStatus
    sources: list[dict[str, Any]]
    tables: list[dict[str, Any]]
    answer: str
