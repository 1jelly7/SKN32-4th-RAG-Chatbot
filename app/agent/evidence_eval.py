from __future__ import annotations

from app.agent.state import GraphState


async def evidence_eval(state: GraphState) -> GraphState:
    """공통 근거 판정 경계.

    판정 로직은 통합 담당이 소유하고, 도메인별 충분성 기준은 재무·판매·RAG 담당과
    협의한다. 이 모듈은 DB나 FAISS에 직접 접근하지 않는다.
    """
    ...
