"""문서와 데이터 근거를 합쳐 결정적 품질 상태를 판정한다.

새 사실을 생성하지 않고 relevance, confidence, metadata, freshness 정책과 명시적 사실
충돌만 평가하며, 채택된 근거만 답변 합성 단계로 전달한다.
"""

from __future__ import annotations

import json
from typing import Any

from app.agent.state import EvidencePolicy, GraphState

DEFAULT_EVIDENCE_POLICY = EvidencePolicy()


async def evidence_eval(
    state: GraphState,
    policy: EvidencePolicy | None = None,
) -> GraphState:
    """분리된 문서·데이터 근거를 정책에 따라 결정적으로 판정한다.

    낮은 품질은 ``INSUFFICIENT`` 또는 부분 채택으로 처리하고, ``CONTRADICTED``는
    명시적 반증이나 동일 fact의 상이한 값에만 사용한다. 계약 문서가 허용하는 1회
    보완 검색은 현재 이 함수에 구현돼 있지 않다.
    """
    document_evidence = state.get("document_evidence") or []
    database_evidence = state.get("database_evidence") or []
    all_evidence = document_evidence + database_evidence

    if state.get("route") == "GENERAL":
        state["evidence"] = []
        state["evidence_status"] = "SUPPORTED"
        state["evidence_reason"] = "일반 질문은 외부 근거가 필요하지 않습니다."
        return state

    active_policy = policy or state.get("evidence_policy", DEFAULT_EVIDENCE_POLICY)
    accepted_evidence = [item for item in all_evidence if _meets_policy(item, active_policy)]
    has_rejected_evidence = len(accepted_evidence) != len(all_evidence)
    has_tool_error = bool(state.get("_errors")) or any(item.get("error") for item in database_evidence)

    has_contradiction = _has_explicit_contradiction(all_evidence) or _has_conflicting_fact_values(all_evidence)
    state["evidence"] = [] if has_contradiction else accepted_evidence

    if has_contradiction:
        state["evidence_status"] = "CONTRADICTED"
        state["evidence_reason"] = "채택 가능한 근거 사이에 명시적인 사실 충돌이 있습니다."
    elif not accepted_evidence:
        state["evidence_status"] = "INSUFFICIENT"
        state["evidence_reason"] = "정책 기준을 충족하는 근거가 없습니다."
    elif has_tool_error or has_rejected_evidence:
        state["evidence_status"] = "PARTIALLY_SUPPORTED"
        state["evidence_reason"] = "일부 조회가 실패했거나 일부 근거가 품질 기준에서 제외됐습니다."
    else:
        state["evidence_status"] = "SUPPORTED"
        state["evidence_reason"] = "수집된 근거가 현재 품질 정책을 충족합니다."
    return state


def _meets_policy(item: dict[str, Any], policy: EvidencePolicy) -> bool:
    """관련성·신뢰도·metadata·freshness 기준을 모두 충족하는지 판단한다."""
    relevance = item.get("relevance", item.get("score", 1.0))
    confidence = item.get("confidence", 1.0)
    if not _is_number_at_least(relevance, policy.min_relevance):
        return False
    if not _is_number_at_least(confidence, policy.min_confidence):
        return False

    metadata = item.get("metadata", {})
    if policy.required_metadata_keys:
        if not isinstance(metadata, dict):
            return False
        if any(metadata.get(key) is None for key in policy.required_metadata_keys):
            return False

    if policy.max_freshness_seconds is not None:
        freshness_seconds = metadata.get("freshness_seconds") if isinstance(metadata, dict) else None
        if not _is_number_at_most(freshness_seconds, policy.max_freshness_seconds):
            return False
    return True


def _is_number_at_least(value: object, threshold: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= threshold


def _is_number_at_most(value: object, threshold: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value <= threshold


def _has_explicit_contradiction(evidence: list[dict[str, Any]]) -> bool:
    return any(item.get("contradicted") is True for item in evidence)


def _has_conflicting_fact_values(evidence: list[dict[str, Any]]) -> bool:
    """같은 fact_id가 서로 다른 명시적 값을 주장할 때만 상충으로 본다."""
    values_by_fact_id: dict[str, set[str]] = {}
    for item in evidence:
        fact_id = item.get("fact_id")
        if not isinstance(fact_id, str) or "fact_value" not in item:
            continue
        normalized_value = json.dumps(item["fact_value"], ensure_ascii=False, sort_keys=True, default=str)
        values_by_fact_id.setdefault(fact_id, set()).add(normalized_value)
    return any(len(values) > 1 for values in values_by_fact_id.values())
