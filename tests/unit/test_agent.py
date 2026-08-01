"""app/agent(router, evidence_eval, graph)를 검증합니다.

MySQL(erp_system/purchase/sales)이 로컬에 준비되어 있으면 전체 그래프까지
실제로 실행해서 검증하고, 없으면 자동으로 건너뜁니다.
"""

from __future__ import annotations

import pytest

from app.agent.llm import FakeLLMPort
from app.agent.nodes import _build_sources, _build_tables, answer_synthesis, database_retrieval, route_data_domain, route_question, router
from app.agent.state import DataDomain, EvidencePolicy, GraphState, Route


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
async def test_database_retrieval_preserves_database_origin_and_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_purchase_query(question: str) -> list[dict[str, object]]:
        assert question == "구매와 판매 현황"
        return [{"type": "database", "domain": "purchase", "rows": []}]

    async def fake_sales_query(question: str) -> list[dict[str, object]]:
        assert question == "구매와 판매 현황"
        return [{"type": "database", "domain": "sales", "rows": []}]

    monkeypatch.setattr("app.agent.nodes.query_purchase", fake_purchase_query)
    monkeypatch.setattr("app.agent.nodes.query_sales", fake_sales_query)

    result = await database_retrieval({"question": "구매와 판매 현황", "data_domain": "both"})

    assert result["database_evidence"] == [
        {"type": "database", "domain": "purchase", "rows": []},
        {"type": "database", "domain": "sales", "rows": []},
    ]


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


@pytest.mark.asyncio
async def test_database_retrieval_keeps_sales_evidence_when_purchase_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_purchase_query(question: str) -> list[dict[str, object]]:
        raise RuntimeError(question)

    async def fake_sales_query(question: str) -> list[dict[str, object]]:
        assert question == "구매와 판매 현황"
        return [{"type": "database", "domain": "sales", "rows": []}]

    monkeypatch.setattr("app.agent.nodes.query_purchase", failing_purchase_query)
    monkeypatch.setattr("app.agent.nodes.query_sales", fake_sales_query)

    result = await database_retrieval({"question": "구매와 판매 현황", "data_domain": "both"})

    assert result["database_evidence"] == [{"type": "database", "domain": "sales", "rows": []}]
    assert result["_errors"]


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

    assert sources[0]["page"] == 3
    assert sources[0]["updated_at"] == "2026-08-01"
    assert sources[0]["source_version"] == "v3"
    assert sources[1]["table_name"] == "sales_summary"
    assert sources[1]["query_id"] == "q-1"
    assert "file_path" not in sources[0]
    assert "password" not in sources[1]
    assert tables[0]["table_name"] == "sales_summary"
    assert tables[0]["freshness_seconds"] == 30
    assert tables[0]["columns"] == ["customer", "revenue"]


# ------------------------------------------------------------------
# 전체 그래프 (실제 MySQL 필요 - 없으면 skip)
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
            database=settings.document_db_database,
        )
        conn.close()
        return True
    except Exception:
        return False


MYSQL_READY = _mysql_available()
skip_without_mysql = pytest.mark.skipif(not MYSQL_READY, reason="로컬에 MySQL(erp_system/purchase/sales)이 준비되어 있지 않습니다")


@skip_without_mysql
@pytest.mark.asyncio
async def test_graph_document_route_end_to_end():
    from app.agent.graph import get_graph

    graph = get_graph()
    result = await graph.ainvoke({"question": "법인카드 사용 지침이 뭐야"})

    assert result["route"] == "DOCUMENT"
    assert result["answer"]
    assert len(result["sources"]) > 0


@skip_without_mysql
@pytest.mark.asyncio
async def test_graph_database_route_end_to_end():
    from app.agent.graph import get_graph

    graph = get_graph()
    result = await graph.ainvoke({"question": "고객별 매출 순위 알려줘"})

    assert result["route"] == "DATABASE"
    assert result["data_domain"] == "sales"
    assert result["answer"]


@skip_without_mysql
@pytest.mark.asyncio
async def test_graph_both_route_collects_both_evidence():
    from app.agent.graph import get_graph

    graph = get_graph()
    result = await graph.ainvoke({"question": "법인카드 지침이랑 매출 현황 같이 알려줘"})

    assert result["route"] == "BOTH"
    assert len(result["document_evidence"]) > 0
    assert len(result["database_evidence"]) > 0


@skip_without_mysql
@pytest.mark.asyncio
async def test_graph_general_route_skips_retrieval():
    from app.agent.graph import get_graph

    graph = get_graph()
    result = await graph.ainvoke({"question": "오늘 기분이 어때"})

    assert result["route"] == "GENERAL"
    assert result.get("document_evidence", []) == []
    assert result.get("database_evidence", []) == []


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
