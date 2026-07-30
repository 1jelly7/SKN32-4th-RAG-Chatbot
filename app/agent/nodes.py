from __future__ import annotations

from app.agent.state import GraphState, Route


def route_question(question: str) -> Route:
    """질문을 GENERAL/DOCUMENT/DATABASE/BOTH 중 하나로 분류한다.

    1차 MVP는 정책·규정·가이드 같은 문서 키워드와 매출·현황·집계·기간 실적 같은
    데이터 키워드를 결정적으로 판별한다. 두 요구가 함께 있으면 BOTH를, 모호한 경우는
    명세에 따라 비용이 큰 LLM 라우터로만 보완한다. 빈 문자열은 호출 전에 검증한다.
    """
    ...


async def cache_lookup(state: GraphState) -> GraphState:
    """캐시 키를 생성해 답변 캐시를 먼저 조회한다.

    hit이면 answer/sources/route를 상태에 복원하고 ``cached=True``를 설정한다. miss면
    ``cached=False``와 키만 남긴다. 캐시 값의 구조가 손상됐거나 만료됐으면 miss로
    취급하며 LLM/MCP 호출은 절대 여기서 하지 않는다.
    """
    ...


async def router(state: GraphState) -> GraphState:
    """question을 분류해 route 필드에 기록하고 기존 상태를 보존한다."""
    ...


async def document_retrieval(state: GraphState) -> GraphState:
    """Document MCP에 question, 검증된 user_context, top_k를 전달한다.

    응답은 ACL을 통과한 chunk 목록이어야 하며 document_evidence에 저장한다. 반환 필드와
    출처 메타데이터를 검증하고, MCP 실패는 상태의 오류 정책에 따라 처리하여 임의의
    문서 내용이나 직접 FAISS 접근으로 대체하지 않는다.
    """
    ...


async def database_retrieval(state: GraphState) -> GraphState:
    """Data MCP를 통해서만 업무 데이터를 조회해 database_evidence에 저장한다.

    자연어 질문과 사용자 범위를 전달하고 SQL·MySQL에는 직접 접근하지 않는다. 조회
    결과의 실행 시각·SQL 요약·행 수 같은 메타데이터를 보존해 이후 근거 평가와 출처
    표시가 가능해야 한다.
    """
    ...


async def evidence_eval(state: GraphState) -> GraphState:
    """수집 근거의 충분성·ACL·신선도·중복·필터 누락을 평가한다.

    규칙으로 판정 가능한 항목을 우선 검사하고 필요한 경우에만 LLM 검증을 한 번
    사용한다. ``SUPPORTED``/``PARTIALLY_SUPPORTED``/``INSUFFICIENT``/``CONTRADICTED``
    중 하나를 기록하고, 답변에 쓸 검증된 evidence만 남긴다.
    """
    ...


async def answer_synthesis(state: GraphState) -> GraphState:
    """검증된 evidence 범위 안에서 answer와 sources를 만든다.

    GENERAL은 일반 답변을 생성할 수 있지만, 검색 경로는 근거 밖의 사실을 보태지
    않는다. 근거 부족·충돌이면 최대 한 차례 보완 검색 후에도 부족함을 명시하며,
    출처는 document/db 유형과 식별자를 보존해 응답 모델에 맞춘다.
    """
    ...


async def cache_write(state: GraphState) -> GraphState:
    """캐시 미스에서 새로 만든 안전한 답변만 정책 TTL로 저장한다.

    should_cache 결과, evidence 상태, cache_key를 확인한 뒤 answer/sources/route 등
    재사용에 필요한 최소 직렬화 값만 기록한다. 캐시 저장 실패가 사용자 응답 자체를
    실패시키지 않도록 처리한다.
    """
    ...
