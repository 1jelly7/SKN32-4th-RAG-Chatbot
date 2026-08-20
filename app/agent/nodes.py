"""LangGraph의 라우팅, MCP 조회, 답변 직렬화 노드.

조회 노드는 주입된 MCP client만 사용하고 문서 파일·FAISS·SQL에 직접 접근하지 않는다.
문서/DB evidence는 평가 전까지 분리하며 답변 노드는 검증된 evidence만 LLM에 전달한다.
"""

from __future__ import annotations

import asyncio

from collections.abc import Awaitable, Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from app.agent.llm import AsyncLLMPort, complete
from app.agent.prompts import ANSWER_PROMPT, FRESHNESS_ESCAPE_HATCH_PROMPT, NEEDS_LIVE_SEARCH_MARKER
from app.agent.query_classification import classify_question
from app.agent.query_expansion import expand_document_queries
from app.agent.state import DataDomain, GraphState, Route
from app.mcp.client import MCPClient, MCPClientError, MCPNoResultError

SENSITIVE_FIELD_PARTS = ("api_key", "password", "secret", "token", "path", "credential")


def route_question(question: str) -> Route:
    """질문을 GENERAL/DOCUMENT/DATABASE/BOTH 중 하나로 분류한다.

    1차 MVP는 정책·규정·가이드 같은 문서 키워드와 매출·현황·집계·기간 실적 같은
    데이터 키워드를 결정적으로 판별한다. 두 요구가 함께 있으면 BOTH를 반환하며,
    키워드가 없는 질문은 GENERAL로 분류한다. 현재 구현은 LLM fallback을 호출하지 않는다.
    """
    normalized = "".join(question.casefold().split())
    document_terms = (
        "정책", "규정", "가이드", "매뉴얼", "문서", "지침", "절차", "휴가", "휴직", "취업규칙",
        # 아래는 실제 등록된 사내규정 10종의 제목에서 뽑은 단어들입니다.
        # 원래 목록이 일반적인 단어("규정", "지침" 등) 위주라, 구체적인 명사로 질문하면
        # (예: "법인카드", "회계") 하나도 안 걸려서 GENERAL로 잘못 분류되는 문제가 있었습니다.
        "법인카드", "카드", "계약", "복지", "후생", "안전보건", "인사", "직원보수", "보수", "급여", "회계",
    )
    database_terms = (
        "매출", "현황", "집계", "실적", "기간", "판매", "구매", "지출",
        "고객", "공급업체", "재고", "vip", "발주", "미수금", "미지급",
    )
    # "경쟁사/타사" 등 외부 회사에 대한 질문은 매출/판매 같은 단어가 들어있어도
    # 우리 내부 DB로 답할 수 없는 범위 밖 질문이라 DATABASE로 보내면 안 됩니다.
    external_scope_terms = ("경쟁사", "타사", "동종업계", "다른회사")
    has_document = any(term in normalized for term in document_terms)
    has_database = any(term in normalized for term in database_terms) and not any(
        term in normalized for term in external_scope_terms
    )
    if has_document and has_database:
        return "BOTH"
    if has_document:
        return "DOCUMENT"
    if has_database:
        return "DATABASE"

    # 키워드 매칭이 아무 것도 못 잡은 경우에만 임베딩 유사도로 한 번 더 확인합니다.
    # "연차", "징계", "출장비" 같은 어휘 격차는 문자열 매칭으로는 원리적으로 못 잡기
    # 때문에, 여기서 의미 유사도로 보강합니다. 대부분의 질문은 위 키워드 단계에서
    # 이미 끝나므로 임베딩 호출은 애매한 소수의 질문에만 발생합니다.
    if not any(term in normalized for term in external_scope_terms):
        from app.agent.semantic_router import classify_by_similarity

        semantic_route = classify_by_similarity(question)
        if semantic_route in ("DOCUMENT", "DATABASE"):
            return semantic_route  # type: ignore[return-value]
    return "GENERAL"


def route_data_domain(question: str) -> DataDomain:
    """DATABASE/BOTH 경로일 때 purchase(구매/지출)와 sales(판매) 도메인을 판별한다."""
    normalized = "".join(question.casefold().split())
    sales_terms = ("매출", "고객", "판매", "재고", "vip", "여신", "수주")
    purchase_terms = ("구매", "지출", "공급업체", "발주", "미지급", "벤더")
    if any(t in normalized for t in sales_terms) and not any(t in normalized for t in purchase_terms):
        return "sales"
    if any(t in normalized for t in purchase_terms) and not any(t in normalized for t in sales_terms):
        return "purchase"
    # 둘 다 걸리거나 둘 다 안 걸리면 두 도메인 다 조회해서 병합합니다.
    return "both"


async def router(state: GraphState) -> GraphState:
    """question을 분류해 route/query_labels 필드에 기록하고 기존 상태를 보존한다.

    query_labels는 원래 query_classification.classify_question()이 계산하도록
    만들어져 있었지만, 그래프 어디에서도 실제로 호출하는 곳이 없어 항상 빈
    리스트로 남아있던 배선 누락이 있었다(FRESHNESS_SENSITIVE 등 라벨 기반 분기가
    실제로는 절대 못 타는 상태였음 - 2026-08-18 웹 검색 기능 추가 중 발견).
    """
    question = state.get("question", "")
    state["route"] = route_question(question)
    state["query_labels"] = list(classify_question(question))
    if state["route"] in ("DATABASE", "BOTH"):
        state["data_domain"] = route_data_domain(question)
    return state


def _merge_document_evidence(
    merged: dict[tuple[Any, Any], dict[str, Any]],
    items: list[dict[str, Any]],
) -> None:
    """document_id+page를 키로 병합하며, 같은 문서가 다시 나오면 더 높은 점수만 남긴다.

    같은 문서가 원본 질문과 확장 검색어 양쪽에서 걸리는 경우가 흔해서(동의어
    확장은 recall을 넓히는 목적이지 다른 문서를 찾는 게 아니다), 병합 없이 그냥
    이어붙이면 evidence_eval과 답변에 같은 근거가 중복 표시된다.
    """
    for item in items:
        key = (item.get("document_id"), item.get("page"))
        existing = merged.get(key)
        if existing is None or float(item.get("score", 0.0)) > float(existing.get("score", 0.0)):
            merged[key] = item


async def document_retrieval(
    state: GraphState,
    mcp_client: MCPClient | None = None,
) -> GraphState:
    """Document MCP에 question과 top_k를 전달한다.

    Document MCP는 내부 문서 DB에서 파일 경로를 먼저 조회한 뒤 해당 파일만 읽는다.
    응답은 document_evidence에 저장하고, MCP 실패 시 임의 경로의 문서를 직접 읽는
    방식으로 대체하지 않는다.

    질문을 그대로 한 번만 검색하면 "겸직 가능해?"처럼 구어체 질문이 문서의 공식
    용어("이중취업 금지")와 어휘가 달라 못 찾는 경우가 있다. 그래서 1차 검색
    점수가 정책 임계값보다 낮을 때만 expand_document_queries()가 만든 동의어
    검색어로 추가 조회한다 - 1차 점수가 이미 충분하면(강한 직접 매치) 확장 없이
    끝나 MCP 호출이 늘지 않는다.
    """
    if mcp_client is None:
        state["document_evidence"] = []
        state.setdefault("_errors", []).append("document_retrieval 실패: MCP client가 주입되지 않았습니다.")
        return state

    question = state.get("question", "")
    document_search_query = state.get("document_search_query") or question
    search_queries = expand_document_queries(document_search_query)
    if not search_queries:
        search_queries = [document_search_query]

    try:
        first_result = await mcp_client.document_search(
            search_queries[0], top_k=10, user_context=state.get("user_context")
        )
        merged: dict[tuple[Any, Any], dict[str, Any]] = {}
        _merge_document_evidence(merged, first_result)

        policy = state.get("evidence_policy")
        min_document_score = float(getattr(policy, "min_document_score", 0.58))
        direct_score = max((float(item.get("score", 0.0)) for item in merged.values()), default=0.0)

        if len(search_queries) > 1 and direct_score < min_document_score:
            expanded_results = await asyncio.gather(
                *(
                    mcp_client.document_search(query, top_k=10, user_context=state.get("user_context"))
                    for query in search_queries[1:]
                ),
                return_exceptions=True,
            )
            for result in expanded_results:
                if isinstance(result, MCPNoResultError):
                    continue
                if isinstance(result, MCPClientError):
                    # 확장 검색 하나가 실패해도 1차 검색 결과는 이미 확보했으니
                    # 전체를 실패시키지 않고 이번 확장 검색분만 건너뛴다.
                    continue
                if isinstance(result, BaseException):
                    raise result
                _merge_document_evidence(merged, result)

        evidence = list(merged.values())
        state["document_evidence"] = evidence
        # 캐시 키가 실제 문서 인덱스 버전을 참조하도록, MCP metadata에서 뽑아 state에 저장합니다.
        # (이전에는 이 필드가 항상 비어 있어 인덱스가 갱신돼도 캐시가 무효화되지 않았습니다)
        if evidence:
            index_version = evidence[0].get("metadata", {}).get("index_version")
            if index_version:
                state["document_index_version"] = index_version
    except MCPNoResultError as exc:
        # "검색했지만 관련 문서가 0건"은 실패가 아니라 정상적인 빈 결과입니다.
        # _errors/_mcp_errors에 기록하지 않아, evidence_eval이 자연스럽게 INSUFFICIENT로
        # 판정하고(정책에 따라 1회 재조회) 응답도 500/502가 아닌 200으로 나가게 합니다.
        # 다만 왜 없는지 이유는 버리지 않고 보존해서(_no_result_reasons), BOTH 질문에서
        # 다른 쪽만 답변에 나올 때 "왜 이쪽은 안 나왔는지"를 최종 답변에 반영할 수 있게 합니다.
        state["document_evidence"] = []
        state.setdefault("_no_result_reasons", {})["document"] = str(exc)
    except MCPClientError as exc:
        if state.get("route") != "BOTH":
            raise
        state["document_evidence"] = []
        state.setdefault("_errors", []).append("document_retrieval 실패")
        state.setdefault("_mcp_errors", []).append(exc)
    return state


async def database_retrieval(
    state: GraphState,
    mcp_client: MCPClient | None = None,
) -> GraphState:
    """Data MCP를 통해서만 업무 데이터를 조회해 database_evidence에 저장한다.

    state.data_domain에 따라 query_purchase 또는 query_sales를 명시적으로 선택하고 자연어
    질문을 전달한다. SQL·MySQL에는 직접 접근하지 않는다(query_purchase/query_sales
    내부에서만 접근). 조회 결과의 실행 시각·SQL 요약·행 수 같은 메타데이터를 보존해
    이후 근거 평가와 출처 표시가 가능해야 한다.
    """
    if mcp_client is None:
        state["database_evidence"] = []
        state.setdefault("_errors", []).append("database_retrieval 실패: MCP client가 주입되지 않았습니다.")
        return state

    question = state.get("question", "")
    user_context = state.get("user_context")
    domain = state.get("data_domain", "both")
    allows_partial_result = domain == "both" or state.get("route") == "BOTH"

    evidence: list[dict[str, Any]] = []
    retrieval_errors: list[MCPClientError] = []
    if domain in ("purchase", "both"):
        try:
            evidence.extend(await mcp_client.purchase_query(question, user_context=user_context))
        except MCPNoResultError as exc:
            state.setdefault("_no_result_reasons", {})["purchase"] = str(exc)
        except MCPClientError as exc:
            if not allows_partial_result:
                raise
            state.setdefault("_errors", []).append("purchase_retrieval 실패")
            retrieval_errors.append(exc)
    if domain in ("sales", "both"):
        try:
            evidence.extend(await mcp_client.sales_query(question, user_context=user_context))
        except MCPNoResultError as exc:
            state.setdefault("_no_result_reasons", {})["sales"] = str(exc)
        except MCPClientError as exc:
            if not allows_partial_result:
                raise
            state.setdefault("_errors", []).append("sales_retrieval 실패")
            retrieval_errors.append(exc)

    state["database_evidence"] = evidence
    if evidence:
        return state
    if state.get("route") == "BOTH":
        # BOTH 경로에서는 document가 병렬로 도는 형제 브랜치라(app.agent.graph),
        # 이 시점에 document_retrieval이 성공했는지 이 함수는 알 수 없다. 예전
        # 순차 실행 때는 document가 먼저 끝나 있어 state.get("document_evidence")로
        # 확인할 수 있었지만, 병렬에서는 그 값이 항상 "아직 없음"으로 보여 매번
        # 여기서 잘못 raise하게 된다. 대신 진짜 예외를 _mcp_errors에 남겨두면,
        # 두 브랜치가 다 끝난 뒤 evidence_eval이 양쪽 다 근거가 없는 걸 확인하고
        # 이 예외를 다시 꺼내 raise한다(총체적 실패를 "근거 부족"으로 조용히
        # 위장하지 않기 위함).
        if retrieval_errors:
            state.setdefault("_mcp_errors", []).extend(retrieval_errors)
        return state

    previous_errors = state.get("_mcp_errors", [])
    if previous_errors:
        raise previous_errors[0]
    if retrieval_errors:
        raise retrieval_errors[0]
    return state


WebSearchFn = Callable[[str], Awaitable[list[dict[str, Any]]]]


async def _default_web_search(question: str) -> list[dict[str, Any]]:
    """실제 Tavily 호출은 여기서만 import한다(테스트가 fake를 주입할 수 있도록).

    앱 기동 시점에 web_tools를 건드리지 않기 위해 함수 안에서 지연 import한다
    (mcp_servers 도메인 모듈들과 동일한 관례, app/mcp/client.py 참고).
    """
    from mcp_servers.web_tools.search import search_web

    return await search_web(question)


async def answer_synthesis(
    state: GraphState,
    llm: AsyncLLMPort | None = None,
    web_search: WebSearchFn | None = None,
) -> GraphState:
    """검증된 evidence 범위 안에서 answer와 sources를 만든다.

    GENERAL은 일반 답변을 생성할 수 있지만, 검색 경로는 근거 밖의 사실을 보태지
    않는다(근거를 프롬프트에 구조적으로 전달하고, 근거만 사용하라고 명시). 근거
    부족·충돌이면 그 사실을 답변에 명시한다. 출처는 document/db/web 유형과
    식별자를 보존해 응답 모델에 맞춘다.

    web_search는 llm과 같은 방식의 의존성 주입이다 - 테스트가 실제 네트워크를
    타지 않고 고정된 fake 결과(또는 빈 리스트/예외)를 주입할 수 있게 하기 위함.
    프로덕션 경로(app/agent/graph.py)에서는 partial(answer_synthesis, ...,
    web_search=web_search)로 실제 함수를 주입한다.
    """
    route = state.get("route", "GENERAL")
    evidence = state.get("evidence", [])
    evidence_status = state.get("evidence_status", "SUPPORTED")
    query_labels = state.get("query_labels", [])
    question = state.get("question", "")

    if route == "GENERAL" and not evidence:
        needs_search = "FRESHNESS_SENSITIVE" in query_labels
        trial_answer: str | None = None

        # 고정 키워드(query_classification.py)로 못 잡은 GENERAL 질문은, 검색부터
        # 하지 말고 LLM에게 "이 질문에 실시간 정보가 필요한가"를 먼저 한 번 물어본다
        # (방법 B). 키워드 목록은 아무리 늘려도 "지금 비트코인 시세", "삼성전자
        # 주가"처럼 표현이 다른 질문을 다 못 잡는 근본 한계가 있어서, 이게 마지막
        # 안전망이다. 키워드로 이미 확실한 경우에는 이 시험 호출을 건너뛰고 바로
        # 검색한다 - 모든 질문마다 분류용 LLM 호출을 추가하는 것보다 훨씬 저렴하다.
        if not needs_search:
            trial_answer = await complete(FRESHNESS_ESCAPE_HATCH_PROMPT, [], question, llm)
            needs_search = NEEDS_LIVE_SEARCH_MARKER in trial_answer

        if not needs_search:
            # LLM이 스스로 "실시간 정보 없이도 답할 수 있다"고 판단한 경우.
            # 근거 없는 일반 지식 답변이므로 시험 답변을 그대로 최종 답변으로 쓴다.
            state["answer"] = trial_answer or ""
            state["sources"] = []
            state["tables"] = []
            return state

        # 실시간성이 중요한 질문(예: "오늘 기준 금리는?")인데 근거가 전혀 없으면,
        # 웹 검색으로 근거를 보충한다. 검색 자체가 실패하거나(TAVILY_API_KEY 미설정,
        # 네트워크 오류 등) 결과가 없으면, LLM이 오래된 학습 데이터로 추측 답변을
        # 만들지 않도록 안전한 안내 문구로 폴백한다.
        search_fn = web_search or _default_web_search
        try:
            evidence = await search_fn(question)
        except Exception:
            evidence = []
        if not evidence:
            state["answer"] = (
                "이 질문은 실시간성이 중요한 정보라 정확한 답변을 드리기 어렵습니다. "
                "최신 출처를 직접 확인해 주세요."
            )
            state["sources"] = []
            state["tables"] = []
            return state

    if route != "GENERAL" and evidence_status == "INSUFFICIENT":
        # 내부 문서를 항상 먼저 시도하고(위에서 이미 끝남), 여기 도달했다는 건
        # 사내 자료에서 근거를 못 찾았다는 뜻이다. DOCUMENT 질문에 한해 웹 검색을
        # 마지막 수단으로 시도한다 - 내부정보 우선, 없을 때만 웹 순서를 지키기
        # 위해 DOCUMENT 검색이 이미 실패로 확정된 이 시점에만 웹을 호출한다.
        # DATABASE/BOTH는 매출·구매 같은 사내 고유 데이터라 웹 검색으로 보충할
        # 수 있는 성격이 아니므로 대상에서 제외한다.
        if route == "DOCUMENT":
            search_fn = web_search or _default_web_search
            try:
                web_evidence = await search_fn(question)
            except Exception:
                web_evidence = []
            if web_evidence:
                evidence = web_evidence
                # 아래로 흘러서 웹 근거로 정식 답변 생성(ANSWER_PROMPT)까지 이어진다.
            else:
                state["answer"] = (
                    "사내 자료와 웹 검색 모두에서 관련된 근거를 찾지 못해 답변을 드리기 "
                    "어렵습니다. 질문을 조금 더 구체적으로 해주시겠어요?"
                )
                state["sources"] = []
                state["tables"] = []
                return state
        else:
            state["answer"] = "사내 자료에서 관련된 근거를 찾지 못해 답변을 드리기 어렵습니다. 질문을 조금 더 구체적으로 해주시겠어요?"
            state["sources"] = []
            state["tables"] = []
            return state

    if route != "GENERAL" and evidence_status == "CONTRADICTED":
        state["answer"] = "서로 모순되는 근거가 확인되어 신뢰할 수 있는 단일 답변을 만들 수 없습니다. 담당자 확인이 필요합니다."
        state["sources"] = []
        state["tables"] = []
        return state

    answer = await complete(ANSWER_PROMPT, evidence, question, llm)
    if evidence_status == "PARTIALLY_SUPPORTED":
        reason = state.get("evidence_reason") or "일부 근거에 조회 오류가 있어, 확인된 부분만 반영한 답변입니다."
        answer += f"\n\n({reason})"

    state["answer"] = answer
    state["sources"] = _build_sources(evidence)
    state["tables"] = _build_tables(evidence)
    return state


def _json_safe(value: Any) -> Any:
    """Decimal/date/datetime처럼 그대로 JSON 직렬화가 안 되는 값을 안전한 타입으로 바꿉니다."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _build_tables(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """database 타입 근거를 프론트엔드가 표/차트로 그릴 수 있는 형태로 변환합니다."""
    tables: list[dict[str, Any]] = []

    for item in evidence:
        if item.get("type") != "database":
            continue

        rows = item.get("rows") or []
        if not rows:
            continue

        columns = [column for column in rows[0] if not _is_sensitive_field_name(column)]
        row_values = [[_json_safe(row.get(col)) for col in columns] for row in rows]

        # 라벨 컬럼(문자열)과 값 컬럼(숫자)을 하나씩 찾아, 막대그래프를 그릴 수 있는지 판단합니다.
        # 값 컬럼은 "마지막" 숫자 컬럼을 우선합니다 - SELECT에서 보통
        # "라벨, 건수, 합계" 순으로 나열되는 경우가 많아, 합계처럼 더 의미 있는
        # 값이 뒤쪽 컬럼에 오는 경우가 많기 때문입니다.
        label_column = None
        value_column = None
        if rows:
            sample = rows[0]
            for col in columns:
                val = sample.get(col)
                if label_column is None and isinstance(val, str):
                    label_column = col
                if isinstance(val, (int, float, Decimal)) and not isinstance(val, bool):
                    value_column = col  # 계속 덮어써서 마지막 숫자 컬럼이 남게 합니다.

        chartable = label_column is not None and value_column is not None and len(rows) <= 30

        tables.append(
            {
                "domain": item.get("domain", "unknown"),
                "sql": item.get("generated_sql", ""),
                "columns": columns,
                "rows": row_values,
                "chartable": chartable,
                "label_column": label_column,
                "value_column": value_column,
                "table_name": _metadata_value(item, "table_name", "view_name"),
                "query_id": _metadata_value(item, "query_id"),
                "freshness_seconds": _metadata_value(item, "freshness_seconds"),
                "source_version": _metadata_value(item, "source_version"),
            }
        )

    return tables


def _build_sources(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """채택된 evidence를 문서별 카드와 DB 출처로 안전하게 직렬화한다."""
    sources: list[dict[str, Any]] = []
    document_sources: dict[str, dict[str, Any]] = {}
    for item in evidence:
        if item.get("type") == "document":
            document_id = item["document_id"]
            source = document_sources.get(document_id)
            if source is None:
                source = {
                    "id": document_id,
                    "title": item["title"],
                    "file_name": item.get("file_name") or item["title"],
                    "source_type": "document",
                    "document_id": document_id,
                    "score": item.get("score"),
                    "pages": [],
                    "chunks": [],
                    "download_url": f"/api/documents/download?doc_id={quote(document_id, safe='')}",
                    "updated_at": _metadata_value(item, "updated_at"),
                    "source_version": _metadata_value(item, "source_version", "index_version"),
                }
                document_sources[document_id] = source
                sources.append(source)
            elif isinstance(item.get("score"), (int, float)) and (
                source["score"] is None or item["score"] > source["score"]
            ):
                source["score"] = item["score"]

            page = item.get("page")
            if isinstance(page, int):
                source["pages"].append(page)
            source["chunks"].append({"page": page, "text": item.get("content", "")})
        elif item.get("type") == "database":
            sources.append(
                {
                    "id": f"{item.get('domain', 'db')}-sql",
                    "title": f"{item.get('domain', 'database')} 데이터 조회 ({item.get('row_count', 0)}건)",
                    "source_type": "database",
                    "document_id": None,
                    "score": None,
                    "table_name": _metadata_value(item, "table_name", "view_name"),
                    "query_id": _metadata_value(item, "query_id"),
                    "freshness_seconds": _metadata_value(item, "freshness_seconds"),
                    "source_version": _metadata_value(item, "source_version"),
                }
            )
        elif item.get("type") == "web":
            sources.append(
                {
                    "id": item.get("url", ""),
                    "title": item.get("title", ""),
                    "source_type": "web",
                    "document_id": None,
                    "url": item.get("url", ""),
                    "score": item.get("score"),
                }
            )
    for source in document_sources.values():
        source["pages"] = sorted(set(source["pages"]))
        source["chunks"] = _sort_unique_source_chunks(source["chunks"])
    return sources


def _sort_unique_source_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """질의 확장으로 중복된 같은 페이지 발췌문은 한 번만 카드에 남긴다."""
    unique_chunks: dict[tuple[int | None, str], dict[str, Any]] = {}
    for chunk in chunks:
        page = chunk.get("page")
        normalized_page = page if isinstance(page, int) else None
        text = str(chunk.get("text", ""))
        unique_chunks.setdefault((normalized_page, text), {"page": normalized_page, "text": text})
    return sorted(
        unique_chunks.values(),
        key=lambda chunk: (chunk["page"] is None, chunk["page"] or 0, chunk["text"]),
    )


def _metadata_value(item: dict[str, Any], *keys: str) -> Any:
    """evidence metadata에서 우선순위에 따라 첫 유효 값을 읽는다."""
    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        return None
    for key in keys:
        value = metadata.get(key)
        if value is not None:
            return value
    return None


def _is_sensitive_field_name(field_name: object) -> bool:
    """표 응답에서 제거할 내부 경로·자격증명 계열 필드인지 판정한다."""
    return isinstance(field_name, str) and any(part in field_name.casefold() for part in SENSITIVE_FIELD_PARTS)