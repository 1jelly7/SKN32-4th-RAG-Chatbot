"""LangGraph의 라우팅, MCP 조회, 답변 직렬화 노드.

조회 노드는 주입된 MCP client만 사용하고 문서 파일·FAISS·SQL에 직접 접근하지 않는다.
문서/DB evidence는 평가 전까지 분리하며 답변 노드는 검증된 evidence만 LLM에 전달한다.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.agent.llm import AsyncLLMPort, complete
from app.agent.prompts import ANSWER_PROMPT, ROUTER_PROMPT
from app.agent.query_classification import classify_question
from app.agent.query_expansion import expand_document_queries
from app.agent.state import DataDomain, GraphState, Route
from app.logging.performance import record_timing, start_timer
from app.mcp.client import MCPClient, MCPClientError, MCPNoResultError

SENSITIVE_FIELD_PARTS = ("api_key", "password", "secret", "token", "file_path")
CHART_VALUE_COLUMN_PARTS = ("revenue", "amount", "total", "sales")
LLM_ROW_LIMIT = 50


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
        "법인카드", "회사카드", "업무용카드", "카드", "계약", "복지", "후생", "안전보건", "인사", "직원보수", "보수", "급여", "회계",
        "겸직", "겸업", "부업", "이중취업", "영리활동", "외부활동", "사외활동", "취업제한",
        "부당한업무지시", "부당지시", "업무지시거부", "직장내괴롭힘", "고충처리", "부가급여", "부가급부",
        "복리후생", "급여외혜택", "인사규정", "복무규정", "근로조건", "수입금", "수납", "징수",
        "세입", "금전수납", "납부금관리", "특별안전보건교육", "안전보건교육", "산업안전교육", "법정의무교육",
    )
    database_terms = (
        "매출", "현황", "집계", "실적", "기간", "판매", "구매", "지출",
        "고객", "공급업체", "거래처", "협력사", "벤더", "매입현황", "구매실적", "지급현황", "비용집계",
        "구매액", "재고", "vip", "발주", "미수금", "미지급",
    )
    has_document = any(term in normalized for term in document_terms)
    has_database = any(term in normalized for term in database_terms)
    if has_document and has_database:
        return "BOTH"
    if has_document:
        return "DOCUMENT"
    if has_database:
        return "DATABASE"
    return "GENERAL"


def route_data_domain(question: str) -> DataDomain:
    """DATABASE/BOTH 경로일 때 purchase(구매/지출)와 sales(판매) 도메인을 판별한다."""
    normalized = "".join(question.casefold().split())
    sales_terms = ("매출", "고객", "판매", "재고", "vip", "여신", "수주")
    purchase_terms = (
        "구매", "지출", "공급업체", "거래처", "협력사", "발주", "미지급", "벤더", "매입", "지급", "비용집계",
    )
    if any(t in normalized for t in sales_terms) and not any(t in normalized for t in purchase_terms):
        return "sales"
    if any(t in normalized for t in purchase_terms) and not any(t in normalized for t in sales_terms):
        return "purchase"
    # 둘 다 걸리거나 둘 다 안 걸리면 두 도메인 다 조회해서 병합합니다.
    return "both"


async def router(
    state: GraphState,
    llm: AsyncLLMPort | None = None,
) -> GraphState:
    """question을 분류해 route 필드에 기록하고 기존 상태를 보존한다."""
    started_ns = start_timer()
    question = state.get("question", "")
    state["query_labels"] = sorted(classify_question(question))
    deterministic_route = route_question(question)
    if deterministic_route == "GENERAL":
        semantic_route, document_search_query = await semantic_route_question(question, llm)
        state["route"] = semantic_route
        if document_search_query:
            state["document_search_query"] = document_search_query
        state["routing_method"] = "semantic"
    else:
        state["route"] = deterministic_route
        state["routing_method"] = "keyword"
    if state["route"] in ("DATABASE", "BOTH"):
        state["data_domain"] = route_data_domain(question)
    record_timing(state.setdefault("timings_ms", {}), "agent_routing", started_ns)
    return state


async def semantic_route_question(
    question: str,
    llm: AsyncLLMPort | None = None,
) -> tuple[Route, str | None]:
    """키워드로 분류하지 못한 질문의 사내 문서·데이터 의도를 의미적으로 판별한다.

    의미 분류 모델의 오류나 계약 위반은 일반 질문으로 안전하게 폴백한다. 이 함수는
    근거를 생성하지 않고 검색 경로만 선택하며, 실제 사내 사실은 이후 MCP 근거로 검증한다.
    """
    if not question.strip():
        return "GENERAL", None
    try:
        raw_response = await complete(ROUTER_PROMPT, [], question, llm)
    except RuntimeError:
        return "GENERAL", None
    return _parse_semantic_route(raw_response)


def _parse_semantic_route(raw_response: str) -> tuple[Route, str | None]:
    """모델의 JSON 응답에서 허용된 route와 안전한 문서 검색어만 반환한다."""
    text = raw_response.strip()
    object_start = text.find("{")
    object_end = text.rfind("}")
    if object_start < 0 or object_end < object_start:
        return "GENERAL", None
    try:
        payload = json.loads(text[object_start : object_end + 1])
    except json.JSONDecodeError:
        return "GENERAL", None
    route = payload.get("route") if isinstance(payload, dict) else None
    if route not in ("GENERAL", "DOCUMENT", "DATABASE", "BOTH"):
        return "GENERAL", None
    raw_query = payload.get("document_query")
    document_query = raw_query.strip()[:300] if isinstance(raw_query, str) else None
    if route not in ("DOCUMENT", "BOTH") or not document_query:
        document_query = None
    return route, document_query


async def document_retrieval(
    state: GraphState,
    mcp_client: MCPClient | None = None,
) -> GraphState:
    """Document MCP에 question과 top_k를 전달한다.

    Document MCP는 내부 문서 DB에서 파일 경로를 먼저 조회한 뒤 해당 파일만 읽는다.
    응답은 document_evidence에 저장하고, MCP 실패 시 임의 경로의 문서를 직접 읽는
    방식으로 대체하지 않는다.
    """
    if mcp_client is None:
        state["document_evidence"] = []
        state.setdefault("_errors", []).append("document_retrieval 실패: MCP client가 주입되지 않았습니다.")
        return state

    question = state.get("question", "")
    document_search_query = state.get("document_search_query") or question
    search_queries = expand_document_queries(document_search_query)
    started_ns = start_timer()
    try:
        results: list[object] = []
        if search_queries:
            first_results = await asyncio.gather(
                mcp_client.document_search(
                    search_queries[0],
                    top_k=10,
                    user_context=state.get("user_context"),
                ),
                return_exceptions=True,
            )
            results.extend(first_results)

        direct_evidence = [
            item
            for result in results
            if isinstance(result, list)
            for item in result
        ]
        policy = state.get("evidence_policy")
        min_document_score = float(getattr(policy, "min_document_score", 0.38))
        direct_score = max((float(item.get("score", 0.0)) for item in direct_evidence), default=0.0)
        direct_search_failed = any(
            isinstance(result, MCPClientError) and not isinstance(result, MCPNoResultError)
            for result in results
        )
        should_expand = (
            len(search_queries) > 1
            and direct_score < min_document_score
            and not direct_search_failed
        )
        if should_expand:
            expanded_results = await asyncio.gather(
                *(
                    mcp_client.document_search(query, top_k=10, user_context=state.get("user_context"))
                    for query in search_queries[1:]
                ),
                return_exceptions=True,
            )
            results.extend(expanded_results)

        evidence: list[dict[str, Any]] = []
        retrieval_errors: list[MCPClientError] = []
        for result in results:
            if isinstance(result, MCPNoResultError):
                continue
            if isinstance(result, MCPClientError):
                retrieval_errors.append(result)
                continue
            if isinstance(result, BaseException):
                raise result
            evidence.extend(result)

        state["document_evidence"] = _merge_document_evidence(evidence, limit=10)
        if retrieval_errors:
            if not state["document_evidence"] and state.get("route") != "BOTH":
                raise retrieval_errors[0]
            state.setdefault("_errors", []).append("document_retrieval 일부 실패")
            state.setdefault("_mcp_errors", []).extend(retrieval_errors)

        # 캐시 키가 실제 문서 인덱스 버전을 참조하도록, MCP metadata에서 뽑아 state에 저장합니다.
        # (이전에는 이 필드가 항상 비어 있어 인덱스가 갱신돼도 캐시가 무효화되지 않았습니다)
        if state["document_evidence"]:
            index_version = state["document_evidence"][0].get("metadata", {}).get("index_version")
            if index_version:
                state["document_index_version"] = index_version
    except MCPNoResultError:
        # "검색했지만 관련 문서가 0건"은 실패가 아니라 정상적인 빈 결과입니다.
        # _errors/_mcp_errors에 기록하지 않아, evidence_eval이 자연스럽게 INSUFFICIENT로
        # 판정하고(정책에 따라 1회 재조회) 응답도 500/502가 아닌 200으로 나가게 합니다.
        state["document_evidence"] = []
    except MCPClientError as exc:
        if state.get("route") != "BOTH":
            raise
        state["document_evidence"] = []
        state.setdefault("_errors", []).append("document_retrieval 실패")
        state.setdefault("_mcp_errors", []).append(exc)
    finally:
        record_timing(state.setdefault("timings_ms", {}), "document_mcp", started_ns)
    return state


def _merge_document_evidence(
    evidence: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """확장 검색에서 중복된 문서 청크를 제거하고 관련도 순으로 제한한다."""
    merged: dict[tuple[object, object, object], dict[str, Any]] = {}
    for item in evidence:
        key = (item.get("document_id"), item.get("page"), item.get("content"))
        current = merged.get(key)
        if current is None or float(item.get("score", 0.0)) > float(current.get("score", 0.0)):
            merged[key] = item
    return sorted(merged.values(), key=lambda item: float(item.get("score", 0.0)), reverse=True)[:limit]


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

    started_ns = start_timer()
    evidence: list[dict[str, Any]] = []
    retrieval_errors: list[MCPClientError] = []
    if domain == "both":
        results = await asyncio.gather(
            mcp_client.purchase_query(question, user_context=user_context),
            mcp_client.sales_query(question, user_context=user_context),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, MCPNoResultError):
                state.setdefault("_no_result_messages", []).append(str(result))
            elif isinstance(result, MCPClientError):
                state.setdefault("_errors", []).append("database_retrieval 실패")
                retrieval_errors.append(result)
            elif isinstance(result, BaseException):
                record_timing(state.setdefault("timings_ms", {}), "database_mcp", started_ns)
                raise result
            else:
                evidence.extend(result)
    elif domain == "purchase":
        try:
            evidence.extend(await mcp_client.purchase_query(question, user_context=user_context))
        except MCPNoResultError as exc:
            state.setdefault("_no_result_messages", []).append(str(exc))
        except MCPClientError as exc:
            if not allows_partial_result:
                record_timing(state.setdefault("timings_ms", {}), "database_mcp", started_ns)
                raise
            state.setdefault("_errors", []).append("purchase_retrieval 실패")
            retrieval_errors.append(exc)
    elif domain == "sales":
        try:
            evidence.extend(await mcp_client.sales_query(question, user_context=user_context))
        except MCPNoResultError as exc:
            state.setdefault("_no_result_messages", []).append(str(exc))
        except MCPClientError as exc:
            if not allows_partial_result:
                record_timing(state.setdefault("timings_ms", {}), "database_mcp", started_ns)
                raise
            state.setdefault("_errors", []).append("sales_retrieval 실패")
            retrieval_errors.append(exc)

    state["database_evidence"] = evidence
    record_timing(state.setdefault("timings_ms", {}), "database_mcp", started_ns)
    if evidence or state.get("document_evidence"):
        return state

    previous_errors = state.get("_mcp_errors", [])
    if previous_errors:
        raise previous_errors[0]
    if retrieval_errors:
        raise retrieval_errors[0]
    return state


async def answer_synthesis(
    state: GraphState,
    llm: AsyncLLMPort | None = None,
) -> GraphState:
    """검증된 evidence 범위 안에서 answer와 sources를 만든다.

    GENERAL은 일반 답변을 생성할 수 있지만, 검색 경로는 근거 밖의 사실을 보태지
    않는다(근거를 프롬프트에 구조적으로 전달하고, 근거만 사용하라고 명시). 근거
    부족·충돌이면 그 사실을 답변에 명시한다. 출처는 document/db 유형과 식별자를
    보존해 응답 모델에 맞춘다.
    """
    route = state.get("route", "GENERAL")
    evidence = state.get("evidence", [])
    evidence_status = state.get("evidence_status", "SUPPORTED")
    query_labels = state.get("query_labels", [])

    # 실시간성이 중요한 질문(예: "오늘 기준 금리는?")인데 근거가 전혀 없으면,
    # LLM이 오래된 학습 데이터로 추측 답변을 만들지 않도록 호출 자체를 건너뜁니다.
    if route == "GENERAL" and "FRESHNESS_SENSITIVE" in query_labels and not evidence:
        state["answer"] = (
            "**요약**\n- 최신 근거가 없어 정확한 답변을 제공할 수 없습니다.\n\n"
            "**세부 내용**\n- 실시간성이 중요한 정보이므로 최신 출처 확인이 필요합니다.\n\n"
            "**근거 문서**\n- 확인된 최신 근거 없음"
        )
        state["sources"] = []
        state["tables"] = []
        return state

    if route != "GENERAL" and evidence_status == "INSUFFICIENT":
        no_result_messages = state.get("_no_result_messages", [])
        detail = (
            no_result_messages[0]
            if no_result_messages
            else "관련 키워드와 동의어로 검색했지만 답을 뒷받침할 충분한 근거를 확인하지 못했습니다."
        )
        state["answer"] = (
            "**요약**\n- 확인된 사내 근거가 부족해 답변할 수 없습니다.\n\n"
            f"**세부 내용**\n- {detail}\n\n"
            "**근거 문서**\n- 확인된 근거 없음"
        )
        state["sources"] = []
        state["tables"] = []
        return state

    if route != "GENERAL" and evidence_status == "CONTRADICTED":
        state["answer"] = (
            "**요약**\n- 서로 모순되는 근거가 확인되어 단일 답변을 제시할 수 없습니다.\n\n"
            "**세부 내용**\n- 적용 문서 또는 담당 부서의 확인이 필요합니다.\n\n"
            "**근거 문서**\n- 상충하는 근거가 있어 확정하지 않음"
        )
        state["sources"] = []
        state["tables"] = []
        return state

    question = state.get("question", "")
    llm_started_ns = start_timer()
    answer = await complete(ANSWER_PROMPT, _limit_evidence_for_answer(evidence), question, llm)
    answer = _replace_evidence_labels(answer, evidence)
    record_timing(state.setdefault("timings_ms", {}), "llm_answer", llm_started_ns)
    if evidence_status == "PARTIALLY_SUPPORTED":
        answer += "\n\n(일부 근거에 조회 오류가 있어, 확인된 부분만 반영한 답변입니다.)"

    state["answer"] = answer
    state["sources"] = _build_sources(evidence)
    state["tables"] = _build_tables(evidence)
    return state


def _replace_evidence_labels(answer: str, evidence: list[dict[str, Any]]) -> str:
    """모델의 내부 근거 번호 표기를 실제 문서명 또는 데이터 조회명으로 바꾼다."""
    def replace(match: re.Match[str]) -> str:
        evidence_index = int(match.group(1)) - 1
        if evidence_index < 0 or evidence_index >= len(evidence):
            return match.group(0)
        item = evidence[evidence_index]
        if item.get("type") == "document":
            title = item.get("title")
            return str(title) if title else match.group(0)
        if item.get("type") == "database":
            return f"{item.get('domain', '업무')} 데이터 조회"
        return match.group(0)

    return re.sub(r"\[근거\s*(\d+)\]", replace, answer)


def _json_safe(value: Any) -> Any:
    """Decimal/date/datetime처럼 그대로 JSON 직렬화가 안 되는 값을 안전한 타입으로 바꿉니다."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _limit_evidence_for_answer(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """화면 표는 보존하면서 답변 프롬프트의 DB 행만 제한한다."""
    limited: list[dict[str, Any]] = []
    for item in evidence:
        copied_item = dict(item)
        if copied_item.get("type") == "database" and isinstance(copied_item.get("rows"), list):
            copied_item["rows"] = copied_item["rows"][:LLM_ROW_LIMIT]
        limited.append(copied_item)
    return limited


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

        # 기간 컬럼은 정수여도 라벨로 허용하고, 금액·합계 계열 값을 우선 선택합니다.
        label_column = None
        value_column = None
        if rows:
            sample = rows[0]
            for col in columns:
                val = sample.get(col)
                is_period = col.casefold().endswith(("_month", "_year", "_quarter"))
                if label_column is None and (isinstance(val, str) or is_period):
                    label_column = col
                if isinstance(val, (int, float, Decimal)) and not isinstance(val, bool):
                    if any(part in col.casefold() for part in CHART_VALUE_COLUMN_PARTS):
                        value_column = col
                    elif value_column is None:
                        value_column = col
                    elif not any(part in value_column.casefold() for part in CHART_VALUE_COLUMN_PARTS):
                        value_column = col

        is_time_series = label_column is not None and label_column.casefold().endswith(
            ("_month", "_year", "_quarter")
        )
        chart_type = _metadata_value(item, "chart_hint") or ("line" if is_time_series else "bar")
        max_chart_rows = 60 if chart_type == "line" else 12
        chartable = label_column is not None and value_column is not None and len(rows) <= max_chart_rows

        tables.append(
            {
                "domain": item.get("domain", "unknown"),
                "sql": item.get("generated_sql", ""),
                "columns": columns,
                "rows": row_values,
                "chartable": chartable,
                "chart_type": chart_type if chartable else None,
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
    """채택된 evidence를 내부 경로 없는 공개 출처 목록으로 변환한다."""
    sources: list[dict[str, Any]] = []
    for item in evidence:
        if item.get("type") == "document":
            sources.append(
                {
                    "id": item["document_id"],
                    "title": item["title"],
                    "source_type": "document",
                    "document_id": item["document_id"],
                    "score": item.get("score"),
                    "page": item.get("page"),
                    "updated_at": _metadata_value(item, "updated_at"),
                    "source_version": _metadata_value(item, "source_version", "index_version"),
                }
            )
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
    return sources


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
