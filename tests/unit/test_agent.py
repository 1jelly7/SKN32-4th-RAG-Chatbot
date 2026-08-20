"""app/agent(router, evidence_eval, graph)를 검증합니다.

MySQL(erp_system/purchase/sales)이 로컬에 준비되어 있으면 전체 그래프까지
실제로 실행해서 검증하고, 없으면 자동으로 건너뜁니다.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from app.agent.graph import build_graph
from app.agent.llm import FakeLLMPort
from app.agent.nodes import _build_sources, _build_tables, answer_synthesis, database_retrieval, route_data_domain, route_question, router
from app.agent.state import DataDomain, EvidencePolicy, GraphState, Route
from app.mcp.client import FakeMCPPort, MCPClient


def _tool_success(
    domain: str,
    data: list[dict[str, Any]],
    sources: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "success",
        "domain": domain,
        "message": None,
        "data": data,
        "sources": sources or [],
        "metadata": metadata or {},
    }


# ------------------------------------------------------------------
# route_question / route_data_domain (순수 함수, 외부 의존성 없음)
# ------------------------------------------------------------------
@pytest.mark.parametrize(
    "question,expected",
    [
        ("휴가 규정이 어떻게 되나요", "DOCUMENT"),
        ("법인카드 지침 알려줘", "DOCUMENT"),
        ("고객별 매출 순위 알려줘", "DATABASE"),
        ("공급업체별 지출 총액이 얼마야", "DATABASE"),
        ("법인카드 지침이랑 매출 현황 같이 알려줘", "BOTH"),
        ("오늘 날씨 어때", "GENERAL"),
    ],
)
def test_route_question_classifies_correctly(question: str, expected: Route) -> None:
    assert route_question(question) == expected


def test_route_data_domain_detects_sales() -> None:
    assert route_data_domain("고객별 매출 순위") == "sales"


def test_route_data_domain_detects_purchase() -> None:
    assert route_data_domain("공급업체별 지출 총액") == "purchase"


def test_route_data_domain_defaults_to_both_when_ambiguous() -> None:
    assert route_data_domain("이번 분기 실적 알려줘") == "both"


def test_route_data_domain_uses_both_for_purchase_and_sales_terms() -> None:
    assert route_data_domain("공급업체 구매와 고객 매출을 비교해줘") == "both"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "expected_route", "expected_domain"),
    [
        ("오늘 날씨 어때", "GENERAL", None),
        ("휴가 규정을 알려줘", "DOCUMENT", None),
        ("공급업체별 지출 총액", "DATABASE", "purchase"),
        ("고객별 매출 순위", "DATABASE", "sales"),
        ("구매와 판매 현황을 알려줘", "DATABASE", "both"),
        ("휴가 규정과 구매 및 판매 현황을 알려줘", "BOTH", "both"),
    ],
)
async def test_router_preserves_route_and_data_domain(
    question: str,
    expected_route: Route,
    expected_domain: DataDomain | None,
) -> None:
    state: GraphState = {"question": question}

    result = await router(state)

    assert result["route"] == expected_route
    assert result.get("data_domain") == expected_domain


@pytest.mark.asyncio
async def test_router_populates_query_labels_for_freshness_sensitive_question() -> None:
    """router()가 classify_question()을 실제로 호출해 query_labels를 채우는지 확인한다.

    이전에는 query_classification.classify_question()이 정의만 되어 있고 그래프
    어디에서도 호출되지 않아, state["query_labels"]가 실제 운영 경로에서는 항상
    빈 리스트였다(answer_synthesis의 FRESHNESS_SENSITIVE 웹 검색 분기가 실제로는
    절대 못 타는 배선 누락 - 2026-08-18 웹 검색 기능 추가 중 발견). 이 테스트는
    그 배선이 실제로 연결돼 있는지를 회귀로 고정한다.
    """
    state: GraphState = {"question": "오늘 원달러 환율 얼마야?"}

    result = await router(state)

    assert "FRESHNESS_SENSITIVE" in result["query_labels"]


@pytest.mark.asyncio
async def test_router_query_labels_empty_for_ordinary_general_question() -> None:
    state: GraphState = {"question": "사과는 무슨색이야"}

    result = await router(state)

    assert "FRESHNESS_SENSITIVE" not in result["query_labels"]


@pytest.mark.asyncio
async def test_database_retrieval_preserves_database_origin_and_domain(
) -> None:
    port = FakeMCPPort(
        {
            "search_documents": _tool_success("document", []),
            "query_purchase": _tool_success("purchase", [{"amount": 100}]),
            "query_sales": _tool_success("sales", [{"revenue": 200}]),
        }
    )
    mcp_client = MCPClient(port)

    result = await database_retrieval(
        {"question": "구매와 판매 현황", "data_domain": "both"},
        mcp_client,
    )

    assert [item["domain"] for item in result["database_evidence"]] == ["purchase", "sales"]
    assert [call.tool_name for call in port.calls] == ["query_purchase", "query_sales"]


# ------------------------------------------------------------------
# evidence_eval (순수 함수, 외부 의존성 없음)
# ------------------------------------------------------------------
@pytest.mark.asyncio
async def test_evidence_eval_insufficient_when_no_evidence():
    from app.agent.evidence_eval import evidence_eval

    state = {"route": "DOCUMENT", "document_evidence": [], "database_evidence": []}
    result = await evidence_eval(state)
    assert result["evidence_status"] == "INSUFFICIENT"


@pytest.mark.asyncio
async def test_evidence_eval_supported_when_evidence_present():
    from app.agent.evidence_eval import evidence_eval

    state = {
        "route": "DOCUMENT",
        "document_evidence": [{"type": "document", "content": "내용"}],
        "database_evidence": [],
    }
    result = await evidence_eval(state)
    assert result["evidence_status"] == "SUPPORTED"


@pytest.mark.asyncio
async def test_evidence_eval_uses_calibrated_document_score_threshold() -> None:
    from app.agent.evidence_eval import evidence_eval

    state: GraphState = {
        "route": "DOCUMENT",
        "document_evidence": [
            {"type": "document", "content": "휴가 규정", "score": 0.8},
            {"type": "document", "content": "낮은 점수", "score": 0.2},
        ],
        "database_evidence": [],
    }

    result = await evidence_eval(state)

    assert result["evidence_status"] == "SUPPORTED"
    assert result["evidence"] == [state["document_evidence"][0]]


@pytest.mark.asyncio
async def test_evidence_eval_general_route_skips_check():
    from app.agent.evidence_eval import evidence_eval

    state = {"route": "GENERAL"}
    result = await evidence_eval(state)
    assert result["evidence_status"] == "SUPPORTED"
    assert result["evidence"] == []


@pytest.mark.asyncio
async def test_evidence_eval_marks_partial_when_one_tool_failed() -> None:
    from app.agent.evidence_eval import evidence_eval

    document_evidence = [{"type": "document", "content": "휴가 규정", "score": 0.9}]
    state: GraphState = {
        "route": "BOTH",
        "document_evidence": document_evidence,
        "database_evidence": [],
        "_errors": ["sales_retrieval 실패"],
    }

    result = await evidence_eval(state)

    assert result["evidence_status"] == "PARTIALLY_SUPPORTED"
    assert result["document_evidence"] == document_evidence
    assert result["database_evidence"] == []
    assert result["evidence"] == document_evidence


@pytest.mark.asyncio
async def test_evidence_eval_uses_injected_quality_policy() -> None:
    from app.agent.evidence_eval import evidence_eval

    policy = EvidencePolicy(
        min_relevance=0.7,
        min_confidence=0.8,
        required_metadata_keys=("source_version",),
        max_freshness_seconds=60,
    )
    valid_document = {
        "type": "document",
        "content": "정책",
        "relevance": 0.9,
        "confidence": 0.9,
        "metadata": {"source_version": "v1", "freshness_seconds": 30},
    }
    stale_database = {
        "type": "database",
        "domain": "sales",
        "relevance": 0.9,
        "confidence": 0.9,
        "metadata": {"source_version": "v1", "freshness_seconds": 120},
    }
    state: GraphState = {
        "route": "BOTH",
        "document_evidence": [valid_document],
        "database_evidence": [stale_database],
    }

    result = await evidence_eval(state, policy)

    assert result["evidence_status"] == "PARTIALLY_SUPPORTED"
    assert result["evidence"] == [valid_document]
    assert result["document_evidence"] == [valid_document]
    assert result["database_evidence"] == [stale_database]


@pytest.mark.asyncio
async def test_evidence_eval_low_confidence_is_insufficient_not_contradicted() -> None:
    from app.agent.evidence_eval import evidence_eval

    state: GraphState = {
        "route": "DOCUMENT",
        "document_evidence": [{"type": "document", "content": "정책", "confidence": 0.1}],
        "database_evidence": [],
    }

    result = await evidence_eval(state, EvidencePolicy(min_confidence=0.8))

    assert result["evidence_status"] == "INSUFFICIENT"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "document_evidence",
    [
        [{"type": "document", "content": "정책", "contradicted": True}],
        [
            {"type": "document", "content": "정책", "fact_id": "leave-days", "fact_value": 10},
            {"type": "document", "content": "정책", "fact_id": "leave-days", "fact_value": 15},
        ],
    ],
)
async def test_evidence_eval_marks_only_explicit_or_fact_value_conflicts_contradicted(
    document_evidence: list[dict[str, object]],
) -> None:
    from app.agent.evidence_eval import evidence_eval

    result = await evidence_eval(
        {"route": "DOCUMENT", "document_evidence": document_evidence, "database_evidence": []}
    )

    assert result["evidence_status"] == "CONTRADICTED"
    assert result["evidence"] == []


@pytest.mark.asyncio
async def test_answer_synthesis_does_not_call_llm_for_contradicted_evidence() -> None:
    fake_llm = FakeLLMPort("should not be used")
    state: GraphState = {
        "route": "DOCUMENT",
        "evidence_status": "CONTRADICTED",
        "evidence": [{"type": "document", "content": "상충 근거"}],
    }

    result = await answer_synthesis(state, fake_llm)

    assert "모순되는 근거" in result["answer"]
    assert result["sources"] == []
    assert result["tables"] == []
    assert fake_llm.calls == []


@pytest.mark.asyncio
async def test_database_retrieval_keeps_sales_evidence_when_purchase_fails(
) -> None:
    port = FakeMCPPort(
        {
            "search_documents": _tool_success("document", []),
            "query_purchase": RuntimeError("구매 조회 실패"),
            "query_sales": _tool_success("sales", [{"revenue": 200}]),
        }
    )
    mcp_client = MCPClient(port)

    result = await database_retrieval(
        {"question": "구매와 판매 현황", "data_domain": "both"},
        mcp_client,
    )

    assert result["database_evidence"][0]["domain"] == "sales"
    assert result["_errors"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "expected_calls"),
    [
        ("오늘 날씨 어때", []),
        ("휴가 규정을 알려줘", ["search_documents"]),
        ("고객별 매출 순위", ["query_sales"]),
    ],
)
async def test_graph_calls_only_allowed_mcp_tools_for_each_route(
    question: str,
    expected_calls: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_complete(prompt: str, context: list[dict[str, Any]], question: str, llm: object = None) -> str:
        return "답변"

    monkeypatch.setattr("app.agent.nodes.complete", fake_complete)
    port = FakeMCPPort(
        {
            "search_documents": _tool_success(
                "document",
                [{"content": "휴가 규정", "score": 0.9}],
                [{"document_id": "policy-1", "title": "휴가 규정"}],
            ),
            "query_purchase": _tool_success("purchase", [{"amount": 100}]),
            "query_sales": _tool_success("sales", [{"revenue": 200}]),
        }
    )

    await build_graph(MCPClient(port)).ainvoke({"question": question})

    assert [call.tool_name for call in port.calls] == expected_calls


@pytest.mark.asyncio
async def test_graph_both_fans_in_document_and_partial_database_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_complete(prompt: str, context: list[dict[str, Any]], question: str, llm: object = None) -> str:
        return "부분 답변"

    monkeypatch.setattr("app.agent.nodes.complete", fake_complete)
    port = FakeMCPPort(
        {
            "search_documents": _tool_success(
                "document",
                [{"content": "휴가 규정", "score": 0.9}],
                [{"document_id": "policy-1", "title": "휴가 규정"}],
            ),
            "query_purchase": {"status": "error", "domain": "purchase", "message": "실패", "error_code": "QUERY_ERROR"},
            "query_sales": _tool_success("sales", [{"revenue": 200}]),
        }
    )

    result = await build_graph(MCPClient(port)).ainvoke({"question": "휴가 규정과 구매 및 판매 현황"})

    # document/database는 이제 병렬로 실행되므로 호출 순서가 보장되지 않는다.
    assert sorted(call.tool_name for call in port.calls) == sorted(
        ["search_documents", "query_purchase", "query_sales"]
    )
    assert len(result["document_evidence"]) == 1
    assert [item["domain"] for item in result["database_evidence"]] == ["sales"]
    assert result["evidence_status"] == "PARTIALLY_SUPPORTED"


@pytest.mark.asyncio
async def test_graph_retries_insufficient_evidence_exactly_once() -> None:
    """품질 미달 근거가 무한 조회 없이 한 번만 보강되게 한다."""
    port = FakeMCPPort(
        {
            "search_documents": _tool_success(
                "document",
                [{"content": "관련성이 낮은 문서", "score": 0.1}],
                [{"document_id": "policy-low", "title": "낮은 관련성"}],
            ),
            "query_purchase": _tool_success("purchase", [{"amount": 100}]),
            "query_sales": _tool_success("sales", [{"revenue": 200}]),
        }
    )

    result = await build_graph(MCPClient(port), FakeLLMPort("사용되지 않음"), web_search=_fake_web_search_empty).ainvoke(
        {"question": "휴가 규정 알려줘"}
    )

    assert result["evidence_status"] == "INSUFFICIENT"
    assert result["evidence_retry_count"] == 1
    assert [call.tool_name for call in port.calls] == ["search_documents", "search_documents"]


@pytest.mark.asyncio
async def test_answer_synthesis_uses_only_sanitized_validated_evidence() -> None:
    fake_llm = FakeLLMPort("검증된 답변")
    validated_evidence = [
        {
            "type": "document",
            "document_id": "policy-1",
            "title": "휴가 규정",
            "content": "연차는 15일입니다.",
            "score": 0.9,
            "file_path": "C:/internal/policy.pdf",
            "api_key": "secret-key",
        }
    ]
    state: GraphState = {
        "route": "DOCUMENT",
        "evidence_status": "SUPPORTED",
        "document_evidence": [{"type": "document", "content": "검증 전 근거"}],
        "evidence": validated_evidence,
    }

    result = await answer_synthesis(state, fake_llm)

    assert result["answer"] == "검증된 답변"
    assert fake_llm.calls[0].context == [
        {
            "type": "document",
            "document_id": "policy-1",
            "title": "휴가 규정",
            "content": "연차는 15일입니다.",
            "score": 0.9,
        }
    ]
    assert "file_path" not in result["sources"][0]
    assert "api_key" not in result["sources"][0]


def test_source_and_table_serialization_preserves_safe_metadata_only() -> None:
    evidence = [
        {
            "type": "document",
            "document_id": "policy-1",
            "title": "휴가 규정",
            "content": "내용",
            "score": 0.9,
            "page": 3,
            "file_path": "C:/internal/policy.pdf",
            "metadata": {"updated_at": "2026-08-01", "index_version": "v3", "api_key": "secret"},
        },
        {
            "type": "database",
            "domain": "sales",
            "generated_sql": "SELECT customer, revenue FROM sales_summary",
            "rows": [{"customer": "A사", "revenue": 100, "file_path": "C:/internal/sales.csv"}],
            "row_count": 1,
            "metadata": {
                "table_name": "sales_summary",
                "query_id": "q-1",
                "freshness_seconds": 30,
                "source_version": "v2",
                "password": "secret",
            },
        },
    ]

    sources = _build_sources(evidence)
    tables = _build_tables(evidence)

    assert sources[0]["pages"] == [3]
    assert sources[0]["chunks"] == [{"page": 3, "text": "내용"}]
    assert sources[0]["updated_at"] == "2026-08-01"
    assert sources[0]["source_version"] == "v3"
    assert sources[1]["table_name"] == "sales_summary"
    assert sources[1]["query_id"] == "q-1"
    assert "file_path" not in sources[0]
    assert "password" not in sources[1]
    assert tables[0]["table_name"] == "sales_summary"
    assert tables[0]["freshness_seconds"] == 30
    assert tables[0]["columns"] == ["customer", "revenue"]


def test_document_sources_merge_pages_and_chunks_by_document_id() -> None:
    sources = _build_sources([
        {
            "type": "document", "document_id": "policy-card", "title": "법인카드 규정.pdf",
            "content": "3쪽 발췌", "score": 0.7, "page": 3, "metadata": {"index_version": "v1"},
        },
        {
            "type": "document", "document_id": "policy-card", "title": "법인카드 규정.pdf",
            "content": "12쪽 발췌", "score": 0.9, "page": 12, "metadata": {"index_version": "v1"},
        },
        {
            "type": "document", "document_id": "policy-card", "title": "법인카드 규정.pdf",
            "content": "3쪽 발췌", "score": 0.8, "page": 3, "metadata": {"index_version": "v1"},
        },
    ])

    assert len(sources) == 1
    assert sources[0]["pages"] == [3, 12]
    assert sources[0]["chunks"] == [{"page": 3, "text": "3쪽 발췌"}, {"page": 12, "text": "12쪽 발췌"}]
    assert sources[0]["download_url"] == "/api/documents/download?doc_id=policy-card"
    assert sources[0]["score"] == 0.9


# ------------------------------------------------------------------
# 전체 그래프 + same-process Data MCP + 실제 MySQL (명시적 opt-in)
# ------------------------------------------------------------------
def _mysql_available() -> bool:
    try:
        from app.core.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()
        import pymysql

        conn = pymysql.connect(
            host=settings.mysql_read_host,
            user=settings.mysql_read_user,
            password=settings.mysql_read_password,
            database=settings.sales_db_database,
        )
        conn.close()
        return True
    except Exception:
        return False


MYSQL_READY = os.getenv("RUN_LOCAL_MYSQL_TESTS") == "1" and _mysql_available()
skip_without_mysql = pytest.mark.skipif(not MYSQL_READY, reason="로컬에 MySQL(erp_system/purchase/sales)이 준비되어 있지 않습니다")


@skip_without_mysql
@pytest.mark.asyncio
async def test_graph_sales_route_uses_in_process_data_mcp_and_mysql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """opt-in 테스트가 실제 sales DB를 MCP 경계 뒤에서만 조회하게 한다."""
    from app.mcp.client import InProcessMCPPort

    async def deterministic_sql(question: str, schema: object) -> str:
        return "SELECT 1 AS health_check LIMIT 1"

    monkeypatch.setattr("mcp_servers.data_tools.sales.query.generate_sql", deterministic_sql)
    graph = build_graph(MCPClient(InProcessMCPPort()), FakeLLMPort("판매 조회 완료"))
    result = await graph.ainvoke({"question": "고객별 매출 순위 알려줘"})

    assert result["route"] == "DATABASE"
    assert result["data_domain"] == "sales"
    assert len(result["database_evidence"]) > 0
    assert result["answer"] == "판매 조회 완료"


# ------------------------------------------------------------------
# tables (표/차트 데이터 변환) - 순수 함수, 외부 의존성 없음
# ------------------------------------------------------------------
def test_build_tables_extracts_columns_and_rows():
    from app.agent.nodes import _build_tables

    evidence = [
        {
            "type": "database",
            "domain": "purchase",
            "generated_sql": "SELECT vendor_name, total FROM x;",
            "rows": [{"vendor_name": "A사", "total": 100}, {"vendor_name": "B사", "total": 200}],
        }
    ]
    tables = _build_tables(evidence)

    assert len(tables) == 1
    assert tables[0]["columns"] == ["vendor_name", "total"]
    assert tables[0]["rows"] == [["A사", 100], ["B사", 200]]


def test_build_tables_converts_decimal_to_float():
    from decimal import Decimal

    from app.agent.nodes import _build_tables

    evidence = [
        {
            "type": "database",
            "domain": "purchase",
            "generated_sql": "x",
            "rows": [{"amount": Decimal("123.45")}],
        }
    ]
    tables = _build_tables(evidence)

    assert tables[0]["rows"][0][0] == 123.45
    assert isinstance(tables[0]["rows"][0][0], float)


def test_build_tables_marks_chartable_when_label_and_value_present():
    from app.agent.nodes import _build_tables

    evidence = [
        {
            "type": "database",
            "domain": "sales",
            "generated_sql": "x",
            "rows": [{"customer": "A", "revenue": 1000}, {"customer": "B", "revenue": 2000}],
        }
    ]
    tables = _build_tables(evidence)

    assert tables[0]["chartable"] is True
    assert tables[0]["label_column"] == "customer"
    assert tables[0]["value_column"] == "revenue"


def test_build_tables_prefers_last_numeric_column_as_value():
    from app.agent.nodes import _build_tables

    evidence = [
        {
            "type": "database",
            "domain": "purchase",
            "generated_sql": "x",
            "rows": [{"vendor": "A", "po_count": 3, "total_spend": 50000}],
        }
    ]
    tables = _build_tables(evidence)

    assert tables[0]["value_column"] == "total_spend"


def test_build_tables_not_chartable_without_label_column():
    from app.agent.nodes import _build_tables

    evidence = [{"type": "database", "domain": "purchase", "generated_sql": "x", "rows": [{"count": 5, "total": 10}]}]
    tables = _build_tables(evidence)

    assert tables[0]["chartable"] is False


def test_build_tables_skips_document_evidence():
    from app.agent.nodes import _build_tables

    evidence = [{"type": "document", "content": "문서 내용"}]
    tables = _build_tables(evidence)
    assert tables == []


def test_build_tables_skips_empty_rows():
    from app.agent.nodes import _build_tables

    evidence = [{"type": "database", "domain": "purchase", "generated_sql": "x", "rows": []}]
    tables = _build_tables(evidence)
    assert tables == []


def test_query_classifier_keeps_stable_general_knowledge_answerable() -> None:
    from app.agent.query_classification import classify_question, requires_verified_context

    labels = classify_question("사과는 무슨 색인가?")

    assert labels == {"GENERAL_KNOWLEDGE"}
    assert requires_verified_context(labels) is False


@pytest.mark.asyncio
async def test_general_answer_receives_question_without_retrieval_context() -> None:
    from app.agent.prompts import FRESHNESS_ESCAPE_HATCH_PROMPT

    fake_llm = FakeLLMPort("사과는 일반적으로 빨간색입니다.")

    result = await answer_synthesis(
        {
            "question": "사과는 무슨 색인가?",
            "route": "GENERAL",
            "query_labels": ["GENERAL_KNOWLEDGE"],
            "evidence": [],
            "evidence_status": "SUPPORTED",
        },
        fake_llm,
    )

    # FRESHNESS_SENSITIVE 라벨이 없는 GENERAL 질문은 이제 방법 B(시험 답변으로
    # 실시간 정보 필요 여부를 LLM 스스로 판단) 경로를 탄다. NEEDS_LIVE_SEARCH
    # 마커가 없으면 그 시험 답변이 그대로 최종 답변이 된다 - ANSWER_PROMPT가
    # 아니라 FRESHNESS_ESCAPE_HATCH_PROMPT로 딱 한 번만 호출된다.
    assert result["answer"] == "사과는 일반적으로 빨간색입니다."
    assert len(fake_llm.calls) == 1
    assert fake_llm.calls[0].question == "사과는 무슨 색인가?"
    assert fake_llm.calls[0].prompt == FRESHNESS_ESCAPE_HATCH_PROMPT


def test_answer_prompt_still_allows_brief_general_knowledge_answers() -> None:
    """ANSWER_PROMPT 자체(evidence가 있어서 이 프롬프트로 실제로 흘러가는 경로)의
    내용 계약을 별도로 고정한다 - 위 테스트가 방법 B 경로로 옮겨가면서 이 문구
    검증이 묻힐 뻔했다."""
    from app.agent.prompts import ANSWER_PROMPT

    assert "사내 자료와 무관한 일반 질문은 간결하게 답할 수 있지만" in ANSWER_PROMPT


def test_answer_prompt_forbids_inventing_article_numbers_for_web_evidence() -> None:
    """실제 사고 재현 회귀 테스트(2026-08-19): 웹 검색 근거(Tavily)로 답변할 때, LLM이
    "적극행정 운영규정 제2조", "국가공무원법 제50조의2"처럼 evidence에 없는 조항
    번호를 근거 문서 섹션에 지어내는 문제가 실제로 발생했다. ANSWER_PROMPT가
    "근거 문서에 조항·페이지를 기재하라"는 지시만 하고 웹 근거는 조항이 없다는
    걸 명시하지 않아서 생긴 문제라, 프롬프트 문구 자체에 그 예외가 있는지 고정한다.
    """
    from app.agent.prompts import ANSWER_PROMPT

    assert "웹 검색 근거는 조항·페이지 번호가 없습니다" in ANSWER_PROMPT
    assert "조항 번호를 지어내지" in ANSWER_PROMPT


@pytest.mark.asyncio
async def test_web_evidence_produces_web_source_cards_not_document_cards() -> None:
    """웹 검색으로 채워진 evidence가 _build_sources를 거쳐 source_type='web' 카드로
    나오는지 확인한다(document 카드로 잘못 나오면 프론트엔드 renderSources()가
    document_sources 필터에서 걸러버려 화면에 아예 안 보이게 된다 - 실제 사고 재현)."""
    from app.agent.prompts import NEEDS_LIVE_SEARCH_MARKER

    fake_llm = FakeLLMPort(NEEDS_LIVE_SEARCH_MARKER)

    async def fake_web_search(question: str) -> list[dict[str, Any]]:
        return [{"type": "web", "title": "적극행정 운영규정 개정", "url": "https://korea.kr/news/1", "content": "..."}]

    result = await answer_synthesis(
        {
            "question": "적극행정 개정사항에 대해 알려줘",
            "route": "GENERAL",
            "query_labels": [],
            "evidence": [],
            "evidence_status": "SUPPORTED",
        },
        fake_llm,
        web_search=fake_web_search,
    )

    assert result["sources"][0]["source_type"] == "web"
    assert result["sources"][0]["url"] == "https://korea.kr/news/1"


async def _fake_web_search_empty(question: str) -> list[dict[str, Any]]:
    """웹 검색이 결과 없이 끝난 상황을 흉내낸다(TAVILY_API_KEY 미설정 등)."""
    return []


@pytest.mark.asyncio
async def test_freshness_question_without_source_uses_specific_safe_fallback() -> None:
    """웹 검색이 빈 결과를 주면, 기존과 동일하게 안전한 안내 문구로 폴백한다."""
    fake_llm = FakeLLMPort("should not be called")

    result = await answer_synthesis(
        {
            "question": "오늘 기준 미국 기준금리는?",
            "route": "GENERAL",
            "query_labels": ["FRESHNESS_SENSITIVE"],
            "evidence": [],
            "evidence_status": "SUPPORTED",
        },
        fake_llm,
        web_search=_fake_web_search_empty,
    )

    assert "최신 출처" in result["answer"]
    assert fake_llm.calls == []


@pytest.mark.asyncio
async def test_freshness_question_with_web_results_generates_grounded_answer() -> None:
    """웹 검색이 결과를 주면, 그 결과를 근거로 LLM이 실제로 호출되고 web 출처가 만들어진다."""
    fake_llm = FakeLLMPort("2026년 8월 기준 기준금리는 ...")

    async def fake_web_search(question: str) -> list[dict[str, Any]]:
        return [
            {
                "type": "web",
                "title": "미국 기준금리 현황",
                "url": "https://example.com/rate",
                "content": "2026년 8월 기준 미국 기준금리는 4.25~4.50%다.",
                "score": 0.9,
            }
        ]

    result = await answer_synthesis(
        {
            "question": "오늘 기준 미국 기준금리는?",
            "route": "GENERAL",
            "query_labels": ["FRESHNESS_SENSITIVE"],
            "evidence": [],
            "evidence_status": "SUPPORTED",
        },
        fake_llm,
        web_search=fake_web_search,
    )

    assert len(fake_llm.calls) == 1
    assert result["sources"] == [
        {
            "id": "https://example.com/rate",
            "title": "미국 기준금리 현황",
            "source_type": "web",
            "document_id": None,
            "url": "https://example.com/rate",
            "score": 0.9,
        }
    ]


@pytest.mark.asyncio
async def test_freshness_question_web_search_exception_falls_back_safely() -> None:
    """웹 검색 자체가 예외를 던져도(네트워크 오류 등) 안전한 안내 문구로 폴백한다."""
    fake_llm = FakeLLMPort("should not be called")

    async def failing_web_search(question: str) -> list[dict[str, Any]]:
        raise RuntimeError("TAVILY_API_KEY가 설정되지 않아 웹 검색을 쓸 수 없습니다.")

    result = await answer_synthesis(
        {
            "question": "오늘 기준 미국 기준금리는?",
            "route": "GENERAL",
            "query_labels": ["FRESHNESS_SENSITIVE"],
            "evidence": [],
            "evidence_status": "SUPPORTED",
        },
        fake_llm,
        web_search=failing_web_search,
    )

    assert "최신 출처" in result["answer"]
    assert fake_llm.calls == []



@pytest.mark.asyncio
async def test_document_route_falls_back_to_web_search_when_internal_insufficient() -> None:
    """"내부정보 우선, 없으면 웹검색" 요구사항: DOCUMENT 질문이 사내 자료에서
    근거를 못 찾으면(INSUFFICIENT), 그때서야 웹 검색으로 보충한다."""
    fake_llm = FakeLLMPort("웹 검색 결과 기반 답변")

    async def fake_web_search(question: str) -> list[dict[str, Any]]:
        return [{"type": "web", "title": "적극행정 운영규정", "url": "https://law.go.kr/x", "content": "..."}]

    result = await answer_synthesis(
        {
            "question": "적극행정 개정사항 알려줘",
            "route": "DOCUMENT",
            "evidence": [],
            "evidence_status": "INSUFFICIENT",
        },
        fake_llm,
        web_search=fake_web_search,
    )

    assert result["sources"][0]["source_type"] == "web"
    assert result["answer"] == "웹 검색 결과 기반 답변"


@pytest.mark.asyncio
async def test_document_route_reports_not_found_when_web_search_also_empty() -> None:
    """내부 자료도 없고 웹 검색도 결과가 없으면, 둘 다 확인했다는 걸 명확히 안내한다."""
    fake_llm = FakeLLMPort("should not be called")

    async def empty_web_search(question: str) -> list[dict[str, Any]]:
        return []

    result = await answer_synthesis(
        {
            "question": "아무도 모르는 질문",
            "route": "DOCUMENT",
            "evidence": [],
            "evidence_status": "INSUFFICIENT",
        },
        fake_llm,
        web_search=empty_web_search,
    )

    assert "사내 자료와 웹 검색 모두에서" in result["answer"]
    assert fake_llm.calls == []


@pytest.mark.asyncio
async def test_database_route_does_not_fall_back_to_web_search_when_insufficient() -> None:
    """DATABASE/BOTH는 매출·구매 같은 사내 고유 데이터라 웹 검색 대상이 아니다 -
    내부정보 우선 정책이 DOCUMENT에만 적용되는지 고정한다."""
    fake_llm = FakeLLMPort("should not be called")
    search_calls: list[str] = []

    async def spy_web_search(question: str) -> list[dict[str, Any]]:
        search_calls.append(question)
        return []

    result = await answer_synthesis(
        {
            "question": "고객별 매출 순위",
            "route": "DATABASE",
            "evidence": [],
            "evidence_status": "INSUFFICIENT",
        },
        fake_llm,
        web_search=spy_web_search,
    )

    assert search_calls == []
    assert "사내 자료에서 관련된 근거를 찾지 못해" in result["answer"]

@pytest.mark.asyncio
async def test_escape_hatch_general_answer_without_marker_skips_search() -> None:
    """방법 B: 키워드로 안 잡힌 GENERAL 질문 - LLM이 스스로 답할 수 있다고 판단하면
    검색을 아예 안 하고, 시험 답변 호출 한 번으로 끝난다."""
    from app.agent.prompts import FRESHNESS_ESCAPE_HATCH_PROMPT

    fake_llm = FakeLLMPort("파이썬 리스트는 append()로 원소를 추가합니다.")
    search_calls: list[str] = []

    async def spy_web_search(question: str) -> list[dict[str, Any]]:
        search_calls.append(question)
        return []

    result = await answer_synthesis(
        {
            "question": "파이썬 리스트에 원소 추가하는 법",
            "route": "GENERAL",
            "query_labels": [],  # FRESHNESS_SENSITIVE 없음 - 키워드로는 안 잡힌 케이스
            "evidence": [],
            "evidence_status": "SUPPORTED",
        },
        fake_llm,
        web_search=spy_web_search,
    )

    assert search_calls == []  # 검색이 아예 호출되지 않아야 함
    assert len(fake_llm.calls) == 1
    assert fake_llm.calls[0].prompt == FRESHNESS_ESCAPE_HATCH_PROMPT
    assert result["answer"] == "파이썬 리스트는 append()로 원소를 추가합니다."


@pytest.mark.asyncio
async def test_escape_hatch_marker_triggers_search_and_final_generation() -> None:
    """방법 B: 키워드로 안 잡힌 질문이라도, LLM이 스스로 실시간 정보가 필요하다고
    판단하면(NEEDS_LIVE_SEARCH 마커) 검색을 트리거하고, 검색 결과로 최종 답변을
    다시 생성한다 - 시험 호출 1회 + 최종 생성 1회, 총 2회 호출된다."""
    from app.agent.prompts import ANSWER_PROMPT, FRESHNESS_ESCAPE_HATCH_PROMPT, NEEDS_LIVE_SEARCH_MARKER

    fake_llm = FakeLLMPort(NEEDS_LIVE_SEARCH_MARKER)

    async def fake_web_search(question: str) -> list[dict[str, Any]]:
        return [{"type": "web", "title": "삼성전자 주가", "url": "https://example.com", "content": "..."}]

    result = await answer_synthesis(
        {
            "question": "삼성전자 주가 얼마야?",
            "route": "GENERAL",
            "query_labels": [],  # FRESHNESS_SENSITIVE 없음 - "주가"는 키워드 목록 밖
            "evidence": [],
            "evidence_status": "SUPPORTED",
        },
        fake_llm,
        web_search=fake_web_search,
    )

    assert len(fake_llm.calls) == 2
    assert fake_llm.calls[0].prompt == FRESHNESS_ESCAPE_HATCH_PROMPT
    assert fake_llm.calls[1].prompt == ANSWER_PROMPT
    assert result["sources"][0]["source_type"] == "web"


@pytest.mark.asyncio
async def test_empty_internal_search_is_not_reported_as_mcp_failure() -> None:
    port = FakeMCPPort(
        {
            "search_documents": _tool_success("document", []),
            "query_purchase": _tool_success("purchase", [{"amount": 100}]),
            "query_sales": _tool_success("sales", [{"revenue": 200}]),
        }
    )

    result = await build_graph(MCPClient(port), FakeLLMPort("should not be called"), web_search=_fake_web_search_empty).ainvoke(
        {"question": "우리 회사 복리후생 규정은?"}
    )

    assert result["evidence_status"] == "INSUFFICIENT"
    assert "사내 자료" in result["answer"]
    assert [call.tool_name for call in port.calls] == ["search_documents", "search_documents"]