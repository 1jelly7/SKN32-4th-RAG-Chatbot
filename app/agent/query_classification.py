"""Question risk classification used to select evidence and fallback policy."""

from __future__ import annotations

from typing import Literal

QueryLabel = Literal[
    "GENERAL_KNOWLEDGE",
    "INTERNAL_KNOWLEDGE",
    "FRESHNESS_SENSITIVE",
    "HIGH_STAKES",
    "CITATION_REQUIRED",
    "AMBIGUOUS",
]


def classify_question(question: str) -> set[QueryLabel]:
    """Return deterministic safety labels without treating no retrieval hit as refusal."""
    normalized = question.casefold().strip()
    labels: set[QueryLabel] = set()
    if any(term in normalized for term in ("우리 회사", "사내", "당사", "내부", "인사 규정", "취업규칙", "복리후생")):
        labels.add("INTERNAL_KNOWLEDGE")
    if any(term in normalized for term in ("오늘", "현재", "최신", "2026", "환율", "금리", "날씨", "뉴스", "공시", "today", "current", "latest")):
        labels.add("FRESHNESS_SENSITIVE")
    if any(term in normalized for term in ("법적", "법률", "계약", "의료", "진단", "투자", "금융", "세금")):
        labels.add("HIGH_STAKES")
    if any(term in normalized for term in ("출처", "인용", "근거", "cite", "citation")):
        labels.add("CITATION_REQUIRED")
    if len(normalized) < 4 or normalized in {"이거", "그거", "알려줘", "설명해줘"}:
        labels.add("AMBIGUOUS")
    if not labels:
        labels.add("GENERAL_KNOWLEDGE")
    return labels


def requires_verified_context(labels: set[QueryLabel]) -> bool:
    """Return whether factual claims must be supported by verified context."""
    return bool(labels & {"INTERNAL_KNOWLEDGE", "FRESHNESS_SENSITIVE", "HIGH_STAKES", "CITATION_REQUIRED"})
