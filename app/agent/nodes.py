from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.agent.llm import AsyncLLMPort, complete
from app.agent.prompts import ANSWER_PROMPT
from app.agent.state import DataDomain, GraphState, Route
from app.mcp.client import MCPClient

SENSITIVE_FIELD_PARTS = ("api_key", "password", "secret", "token", "file_path")


def route_question(question: str) -> Route:
    """질문을 GENERAL/DOCUMENT/DATABASE/BOTH 중 하나로 분류한다.

    1차 MVP는 정책·규정·가이드 같은 문서 키워드와 매출·현황·집계·기간 실적 같은
    데이터 키워드를 결정적으로 판별한다. 두 요구가 함께 있으면 BOTH를, 모호한 경우는
    명세에 따라 비용이 큰 LLM 라우터로만 보완한다. 빈 문자열은 호출 전에 검증한다.
    """
    normalized = question.casefold()
    document_terms = ("정책", "규정", "가이드", "매뉴얼", "문서", "지침", "절차", "휴가", "휴직", "취업규칙")
    database_terms = (
        "매출", "현황", "집계", "실적", "기간", "재무", "판매", "구매", "지출",
        "고객", "공급업체", "재고", "vip", "발주", "미수금", "미지급",
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
    normalized = question.casefold()
    sales_terms = ("매출", "고객", "판매", "재고", "vip", "여신", "수주")
    purchase_terms = ("구매", "지출", "공급업체", "발주", "미지급", "벤더", "재무")
    if any(t in normalized for t in sales_terms) and not any(t in normalized for t in purchase_terms):
        return "sales"
    if any(t in normalized for t in purchase_terms) and not any(t in normalized for t in sales_terms):
        return "purchase"
    # 둘 다 걸리거나 둘 다 안 걸리면 두 도메인 다 조회해서 병합합니다.
    return "both"


async def router(state: GraphState) -> GraphState:
    """question을 분류해 route 필드에 기록하고 기존 상태를 보존한다."""
    question = state.get("question", "")
    state["route"] = route_question(question)
    if state["route"] in ("DATABASE", "BOTH"):
        state["data_domain"] = route_data_domain(question)
    return state


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
    try:
        state["document_evidence"] = await mcp_client.document_search(question, top_k=4)
    except Exception as exc:  # noqa: BLE001 - 실패해도 다른 경로 결과로 부분 응답 가능해야 함
        state["document_evidence"] = []
        state.setdefault("_errors", []).append(f"document_retrieval 실패: {exc}")
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
    domain = state.get("data_domain", "both")

    evidence: list[dict[str, Any]] = []
    if domain in ("purchase", "both"):
        try:
            evidence.extend(await mcp_client.purchase_query(question))
        except Exception as exc:  # noqa: BLE001 - 다른 도메인 조회 결과는 보존해야 함
            state.setdefault("_errors", []).append(f"purchase_retrieval 실패: {exc}")
    if domain in ("sales", "both"):
        try:
            evidence.extend(await mcp_client.sales_query(question))
        except Exception as exc:  # noqa: BLE001 - 다른 도메인 조회 결과는 보존해야 함
            state.setdefault("_errors", []).append(f"sales_retrieval 실패: {exc}")

    state["database_evidence"] = evidence
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

    if route != "GENERAL" and evidence_status == "INSUFFICIENT":
        state["answer"] = "관련된 근거를 찾지 못해 답변을 드리기 어렵습니다. 질문을 조금 더 구체적으로 해주시겠어요?"
        state["sources"] = []
        return state

    answer = await complete(ANSWER_PROMPT, evidence, llm)
    if evidence_status == "PARTIALLY_SUPPORTED":
        answer += "\n\n(일부 근거에 조회 오류가 있어, 확인된 부분만 반영한 답변입니다.)"

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
    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        return None
    for key in keys:
        value = metadata.get(key)
        if value is not None:
            return value
    return None


def _is_sensitive_field_name(field_name: object) -> bool:
    return isinstance(field_name, str) and any(part in field_name.casefold() for part in SENSITIVE_FIELD_PARTS)
