from __future__ import annotations

from app.agent.state import GraphState


async def evidence_eval(state: GraphState) -> GraphState:
    """공통 근거 판정 경계.

    1차 MVP는 결정적 규칙으로 판정한다: 근거가 하나도 없으면 INSUFFICIENT,
    DB 근거에 오류가 있으면 PARTIALLY_SUPPORTED(문서 근거가 있으면) 또는
    INSUFFICIENT(근거가 아예 없으면), 그 외에는 SUPPORTED로 본다.
    LLM 기반 정교한 판정으로 교체하려면 이 함수 내부만 바꾸면 되고, 상위(graph.py,
    nodes.py)는 evidence_status 필드 계약만 보고 동작한다.
    """
    document_evidence = state.get("document_evidence") or []
    database_evidence = state.get("database_evidence") or []
    all_evidence = document_evidence + database_evidence

    # GENERAL 경로는 근거 검색을 안 하므로 평가를 건너뜁니다.
    if state.get("route") == "GENERAL":
        state["evidence"] = []
        state["evidence_status"] = "SUPPORTED"
        return state

    if not all_evidence:
        state["evidence"] = []
        state["evidence_status"] = "INSUFFICIENT"
        return state

    # database_evidence 중 오류가 있는 항목이 있는지 확인합니다.
    has_db_error = any(item.get("error") for item in database_evidence if item.get("type") == "database")
    has_db_rows = any(item.get("row_count", 0) > 0 for item in database_evidence if item.get("type") == "database")
    has_doc_evidence = len(document_evidence) > 0

    state["evidence"] = all_evidence

    if has_db_error and not has_db_rows and not has_doc_evidence:
        state["evidence_status"] = "INSUFFICIENT"
    elif has_db_error and (has_doc_evidence or has_db_rows):
        state["evidence_status"] = "PARTIALLY_SUPPORTED"
    else:
        state["evidence_status"] = "SUPPORTED"

    return state
