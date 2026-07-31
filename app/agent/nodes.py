from __future__ import annotations

from app.agent.state import GraphState, Route


def route_question(question: str) -> Route:
    """질문을 GENERAL/DOCUMENT/DATABASE/BOTH 중 하나로 분류한다.

    1차 MVP는 정책·규정·가이드 같은 문서 키워드와 매출·현황·집계·기간 실적 같은
    데이터 키워드를 결정적으로 판별한다. 두 요구가 함께 있으면 BOTH를, 모호한 경우는
    명세에 따라 비용이 큰 LLM 라우터로만 보완한다. 빈 문자열은 호출 전에 검증한다.
    """
    normalized = question.casefold()
    document_terms = ("정책", "규정", "가이드", "매뉴얼", "문서")
    database_terms = ("구매", "구매액", "공급처", "매출", "현황", "집계", "실적", "기간", "판매")
    has_document = any(term in normalized for term in document_terms)
    has_database = any(term in normalized for term in database_terms)
    if has_document and has_database:
        return "BOTH"
    if has_document:
        return "DOCUMENT"
    if has_database:
        return "DATABASE"
    return "GENERAL"


async def router(state: GraphState) -> GraphState:
    """question을 분류해 route 필드에 기록하고 기존 상태를 보존한다."""
    ...


async def document_retrieval(state: GraphState) -> GraphState:
    """Document MCP에 question과 top_k를 전달한다.

    Document MCP는 내부 문서 DB에서 파일 경로를 먼저 조회한 뒤 해당 파일만 읽는다.
    응답은 document_evidence에 저장하고, MCP 실패 시 임의 경로의 문서를 직접 읽는
    방식으로 대체하지 않는다.
    """
    ...


async def database_retrieval(state: GraphState) -> GraphState:
    """Data MCP를 통해서만 업무 데이터를 조회해 database_evidence에 저장한다.

    state.data_domain에 따라 query_purchase 또는 query_sales를 명시적으로 선택하고 자연어
    질문을 전달한다. SQL·MySQL에는 직접 접근하지 않는다. 조회 결과의
    실행 시각·SQL 요약·행 수 같은 메타데이터를 보존해 이후 근거 평가와 출처 표시가
    가능해야 한다.
    """
    ...


async def answer_synthesis(state: GraphState) -> GraphState:
    """검증된 evidence 범위 안에서 answer와 sources를 만든다.

    GENERAL은 일반 답변을 생성할 수 있지만, 검색 경로는 근거 밖의 사실을 보태지
    않는다. 근거 부족·충돌이면 최대 한 차례 보완 검색 후에도 부족함을 명시하며,
    출처는 document/db 유형과 식별자를 보존해 응답 모델에 맞춘다.
    """
    ...
