"""구매 Text2SQL(스키마·가드·EXPLAIN 재시도·프롬프트 결과)의 단위/골든 케이스 테스트.

빠른 테스트(스키마 정합성, 가드 규칙, 재시도 흐름)는 외부 서비스 없이 항상 돈다.
골든 케이스(tests/fixtures/cases/purchase_text2sql_cases.jsonl)는 실제 OpenAI 호출과
purchase_reader/EXPLAIN용 로컬 MySQL이 필요해 tests/unit/test_sales_text2sql.py와
동일한 RUN_LOCAL_MYSQL_TESTS=1 opt-in 패턴으로만 실행한다(AGENTS.md: 단위 테스트는
가능한 한 API key·네트워크·MySQL 없이 실행한다).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from mcp_servers.data_tools.purchase import query as query_module
from mcp_servers.data_tools.purchase import text2sql as text2sql_module
from mcp_servers.data_tools.purchase.schema import get_schema_resource
from mcp_servers.data_tools.purchase.sql_guard import (
    ALLOWED_VIEWS,
    referenced_tables,
    validate_and_normalize,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
CASES_PATH = FIXTURES_DIR / "cases" / "purchase_text2sql_cases.jsonl"

# 옛 schema.sql(10테이블)이 정의했지만 실제 원천 데이터가 없어 정본에서 제외한
# 유령 테이블. 이 이름들이 스키마 리소스 어디에도 다시 나타나면 안 된다.
_PHANTOM_TABLES = (
    "purchase_requisitions",
    "vendor_ratings",
    "invoice_matching",
    "vendor_contracts",
    "procurement_reports",
)


# ---------------------------------------------------------------------------
# 1. 스키마 정합성 (외부 서비스 없음)
# ---------------------------------------------------------------------------


def test_schema_only_advertises_allowed_views() -> None:
    """schema.py의 views 키가 sql_guard의 화이트리스트와 정확히 일치해야 한다."""
    schema = get_schema_resource()
    assert set(schema["views"].keys()) == set(ALLOWED_VIEWS)


def test_schema_has_no_phantom_tables() -> None:
    """실제 원천 데이터가 없는 유령 테이블이 뷰·지표·범위 밖 목록 어디에도 없어야 한다."""
    schema = get_schema_resource()
    haystack = json.dumps(schema, default=str, ensure_ascii=False)
    for phantom in _PHANTOM_TABLES:
        assert (
            phantom not in haystack
        ), f"유령 테이블 '{phantom}'이 스키마 리소스에 남아있습니다."


def test_schema_metrics_reference_allowed_views_only() -> None:
    """지표 정의가 가리키는 뷰도 전부 허용 목록 안에 있어야 한다."""
    schema = get_schema_resource()
    for term, metric in schema["metrics"].items():
        assert (
            metric["view"] in ALLOWED_VIEWS
        ), f"지표 '{term}'이 허용되지 않은 뷰 '{metric['view']}'를 가리킵니다."


def test_purchase_amount_metric_is_defined_once_without_or() -> None:
    """'구매액' 지표 설명에 '또는'이 없어야 한다(정의를 하나로 고정)."""
    schema = get_schema_resource()
    metric = schema["metrics"]["구매액"]
    assert metric["view"] == "v_purchase_order"
    assert metric["column"] == "po_amount"
    assert "또는" not in metric["note"]


def test_fallback_templates_removed() -> None:
    """API 키가 없을 때 질문과 무관한 SQL을 돌려주던 하드코딩이 없어야 한다."""
    for name in (
        "_FALLBACK_TEMPLATES",
        "_DEFAULT_FALLBACK_SQL",
        "_generate_sql_fallback",
    ):
        assert not hasattr(text2sql_module, name), f"{name}이(가) 아직 남아있습니다."


def test_generate_sql_raises_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """API 키가 없으면 조용히 폴백하지 않고 예외를 낸다(server.py가 QUERY_ERROR로 변환)."""
    fake_settings = mock.Mock(openai_api_key="")
    monkeypatch.setattr(text2sql_module, "get_settings", lambda: fake_settings)

    with pytest.raises(RuntimeError):
        asyncio.run(text2sql_module.generate_sql("아무 질문", get_schema_resource()))


# ---------------------------------------------------------------------------
# 1-1. 복합질문 응답 파싱 _extract_queries (외부 서비스 없음)
# ---------------------------------------------------------------------------


def test_extract_queries_returns_empty_list_for_no_sql() -> None:
    assert text2sql_module._extract_queries("NO_SQL") == []
    assert text2sql_module._extract_queries("  no_sql  ") == []


def test_extract_queries_parses_json_array() -> None:
    raw = json.dumps(
        {
            "queries": [
                {
                    "label": "올해 구매액 합계",
                    "sql": "SELECT SUM(po_amount) AS total FROM v_purchase_order",
                },
                {
                    "label": "구매액 최대 공급업체",
                    "sql": "SELECT vendor_name FROM v_purchase_order ORDER BY po_amount DESC LIMIT 1",
                },
            ]
        }
    )
    assert text2sql_module._extract_queries(raw) == [
        {
            "label": "올해 구매액 합계",
            "sql": "SELECT SUM(po_amount) AS total FROM v_purchase_order",
        },
        {
            "label": "구매액 최대 공급업체",
            "sql": "SELECT vendor_name FROM v_purchase_order ORDER BY po_amount DESC LIMIT 1",
        },
    ]


def test_extract_queries_truncates_to_max_sub_queries() -> None:
    """5개를 요청해도 MAX_SUB_QUERIES(3)개까지만 남긴다."""
    raw = json.dumps(
        {
            "queries": [
                {"label": f"항목{i}", "sql": f"SELECT {i} FROM v_purchase_order"}
                for i in range(5)
            ]
        }
    )
    result = text2sql_module._extract_queries(raw)
    assert len(result) == text2sql_module.MAX_SUB_QUERIES == 3


@pytest.mark.parametrize(
    "raw",
    [
        "이건 JSON이 아닙니다",
        "{}",  # "queries" 키 없음
        json.dumps({"queries": "SELECT 1"}),  # queries가 리스트가 아님
    ],
)
def test_extract_queries_returns_empty_list_on_malformed_json(raw: str) -> None:
    """파싱 실패는 예전처럼 무관한 SQL을 돌려주지 않고 빈 리스트로 안전하게 처리한다."""
    assert text2sql_module._extract_queries(raw) == []


def test_extract_queries_skips_items_without_sql() -> None:
    raw = json.dumps(
        {
            "queries": [
                {"label": "빈 항목"},
                {"label": "정상", "sql": "SELECT 1 FROM v_purchase_order"},
            ]
        }
    )
    assert text2sql_module._extract_queries(raw) == [
        {"label": "정상", "sql": "SELECT 1 FROM v_purchase_order"}
    ]


# ---------------------------------------------------------------------------
# 2. SQL 가드 (외부 서비스 없음)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; SELECT 2",
        "UPDATE v_purchase_order SET status='x'",
        "SELECT /* bypass */ 1 FROM v_purchase_order",
        "SELECT * FROM purchase_orders",  # 원본 테이블 — 화이트리스트 밖
        "SELECT * FROM v_purchase_order INTO OUTFILE '/tmp/x.csv'",
    ],
)
def test_guard_rejects_unsafe_sql(sql: str) -> None:
    with pytest.raises(ValueError):
        validate_and_normalize(sql)


def test_guard_appends_default_limit_when_missing() -> None:
    result = validate_and_normalize("SELECT vendor_id FROM v_purchase_order")
    assert "LIMIT 200" in result


def test_guard_caps_limit_above_maximum() -> None:
    result = validate_and_normalize("SELECT vendor_id FROM v_purchase_order LIMIT 5000")
    assert "LIMIT 200" in result
    assert "5000" not in result


def test_guard_keeps_limit_within_maximum() -> None:
    result = validate_and_normalize("SELECT vendor_id FROM v_purchase_order LIMIT 10")
    assert "LIMIT 10" in result


def test_referenced_tables_finds_multiple_joins() -> None:
    sql = "SELECT a.x FROM v_purchase_order a JOIN v_vendor_invoice b ON a.vendor_id = b.vendor_id"
    assert referenced_tables(sql) == {"v_purchase_order", "v_vendor_invoice"}


# ---------------------------------------------------------------------------
# 3. 파이프라인 재시도 흐름 (LLM/DB를 mock으로 대체 — 외부 서비스 없음)
# ---------------------------------------------------------------------------


def test_query_purchase_returns_empty_when_llm_declines() -> None:
    """LLM이 NO_SQL로 답하면(범위 밖) rows=[]를 돌려줘 server.py가 NO_RESULT로 처리한다."""

    # old: async def declines(question: str, schema: Any) -> str: return ""
    # 변경 이유: generate_sql()이 이제 list[dict]를 반환한다. NO_SQL은 빈 리스트로 표현한다.
    async def declines(question: str, schema: Any) -> list[dict[str, str]]:
        return []

    with mock.patch.object(query_module, "generate_sql", declines):
        evidence = asyncio.run(query_module.query_purchase("답할 수 없는 질문"))

    assert evidence[0]["rows"] == []
    assert evidence[0]["domain"] == "purchase"
    assert evidence[0]["metadata"]["retry_count"] == 0


def test_query_purchase_returns_empty_for_blank_question() -> None:
    evidence = asyncio.run(query_module.query_purchase("   "))
    assert evidence[0]["rows"] == []


def test_query_purchase_returns_empty_for_too_long_question() -> None:
    evidence = asyncio.run(query_module.query_purchase("가" * 501))
    assert evidence[0]["rows"] == []


def test_query_purchase_retries_once_on_explain_failure() -> None:
    """EXPLAIN이 실패하면 오류 메시지를 재작성 함수에 넘기고 최대 1회만 재시도한다."""
    calls: list[str] = []

    # old: 아래 두 함수가 단일 문자열(str)을 반환했다.
    # 변경 이유: generate_sql()/generate_sql_with_error()가 이제 list[dict]를
    # 반환한다. _run_single_query()는 재작성 결과의 첫 번째 항목만 사용한다.
    async def first_sql(question: str, schema: Any) -> list[dict[str, str]]:
        return [
            {"label": "테스트", "sql": "SELECT bad_column FROM v_purchase_order LIMIT 5"}
        ]

    async def retried_sql(
        question: str, schema: Any, failed_sql: str, error: str
    ) -> list[dict[str, str]]:
        calls.append(error)
        return [
            {"label": "테스트", "sql": "SELECT vendor_id FROM v_purchase_order LIMIT 5"}
        ]

    def fake_explain(sql: str) -> None:
        if "bad_column" in sql:
            raise RuntimeError("Unknown column 'bad_column'")

    def fake_query_readonly(sql: str) -> list[dict[str, Any]]:
        return [{"vendor_id": 1}]

    with (
        mock.patch.object(query_module, "generate_sql", first_sql),
        mock.patch.object(query_module, "generate_sql_with_error", retried_sql),
        mock.patch.object(query_module, "explain_readonly", fake_explain),
        mock.patch.object(query_module, "query_readonly", fake_query_readonly),
    ):
        evidence = asyncio.run(query_module.query_purchase("아무 질문"))

    assert len(calls) == 1
    assert "bad_column" in calls[0]
    assert evidence[0]["label"] == "테스트"
    assert evidence[0]["metadata"]["retry_count"] == 1
    assert evidence[0]["row_count"] == 1


def test_query_purchase_raises_when_retry_also_fails() -> None:
    """재시도까지 실패하면 예외를 그대로 올려 server.py가 QUERY_ERROR로 변환하게 한다."""

    async def first_sql(question: str, schema: Any) -> list[dict[str, str]]:
        return [
            {"label": "테스트", "sql": "SELECT bad_column FROM v_purchase_order LIMIT 5"}
        ]

    async def retried_sql(
        question: str, schema: Any, failed_sql: str, error: str
    ) -> list[dict[str, str]]:
        return [
            {"label": "테스트", "sql": "SELECT still_bad FROM v_purchase_order LIMIT 5"}
        ]

    def fake_explain(sql: str) -> None:
        raise RuntimeError("always fails")

    with (
        mock.patch.object(query_module, "generate_sql", first_sql),
        mock.patch.object(query_module, "generate_sql_with_error", retried_sql),
        mock.patch.object(query_module, "explain_readonly", fake_explain),
    ):
        with pytest.raises(RuntimeError):
            asyncio.run(query_module.query_purchase("아무 질문"))


# ---------------------------------------------------------------------------
# 3-1. 복합질문 통합 흐름 (LLM/DB를 mock으로 대체 — 외부 서비스 없음)
# ---------------------------------------------------------------------------


def test_query_purchase_handles_compound_question_with_multiple_labels() -> None:
    """복합질문이면 항목마다 label이 붙은 독립 evidence를 병렬로 만든다."""

    async def multi_sql(question: str, schema: Any) -> list[dict[str, str]]:
        return [
            {
                "label": "올해 구매액 합계",
                "sql": "SELECT SUM(po_amount) AS total FROM v_purchase_order",
            },
            {
                "label": "구매액 최대 공급업체",
                "sql": "SELECT vendor_name FROM v_purchase_order ORDER BY po_amount DESC LIMIT 1",
            },
        ]

    def fake_query_readonly(sql: str) -> list[dict[str, Any]]:
        if "SUM(po_amount)" in sql:
            return [{"total": 500}]
        return [{"vendor_name": "Acme"}]

    with (
        mock.patch.object(query_module, "generate_sql", multi_sql),
        mock.patch.object(query_module, "explain_readonly", lambda sql: None),
        mock.patch.object(query_module, "query_readonly", fake_query_readonly),
    ):
        evidence = asyncio.run(
            query_module.query_purchase("올해 구매액과 구매액 최대 공급업체 알려줘")
        )

    assert len(evidence) == 2
    by_label = {item["label"]: item for item in evidence}
    assert by_label["올해 구매액 합계"]["rows"] == [{"total": 500}]
    assert by_label["구매액 최대 공급업체"]["rows"] == [{"vendor_name": "Acme"}]
    for item in evidence:
        assert item["domain"] == "purchase"


def test_query_purchase_keeps_per_item_empty_result_without_dropping_others() -> None:
    """한 항목만 빈 결과여도 다른 항목의 결과는 그대로 남는다."""

    async def multi_sql(question: str, schema: Any) -> list[dict[str, str]]:
        return [
            {"label": "결과 있음", "sql": "SELECT 1 AS total FROM v_purchase_order"},
            {
                "label": "결과 없음",
                "sql": "SELECT 1 AS total FROM v_purchase_order WHERE 1=0",
            },
        ]

    def fake_query_readonly(sql: str) -> list[dict[str, Any]]:
        return [] if "1=0" in sql else [{"total": 1}]

    with (
        mock.patch.object(query_module, "generate_sql", multi_sql),
        mock.patch.object(query_module, "explain_readonly", lambda sql: None),
        mock.patch.object(query_module, "query_readonly", fake_query_readonly),
    ):
        evidence = asyncio.run(query_module.query_purchase("복합질문"))

    assert len(evidence) == 2
    by_label = {item["label"]: item for item in evidence}
    assert by_label["결과 있음"]["rows"] == [{"total": 1}]
    assert by_label["결과 없음"]["rows"] == []
    assert isinstance(by_label["결과 없음"]["message"], str)
    assert by_label["결과 없음"]["message"]


def test_chart_hint_prefers_line_for_period_columns() -> None:
    assert query_module._chart_hint([{"po_month": "2026-01", "total": 1}]) == "line"
    assert query_module._chart_hint([{"vendor_name": "A", "total": 1}]) == "bar"
    assert query_module._chart_hint([]) is None


# ---------------------------------------------------------------------------
# 4. 골든 케이스 — 실제 OpenAI + 로컬 purchase DB 필요 (opt-in)
# ---------------------------------------------------------------------------


def _dependencies_available() -> bool:
    try:
        from app.core.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()
        if not settings.openai_api_key:
            return False

        import pymysql

        conn = pymysql.connect(
            host=settings.purchase_read_host or settings.mysql_read_host,
            user=settings.purchase_read_user,
            password=settings.purchase_read_password,
            database=settings.purchase_read_database or settings.purchase_db_database,
        )
        conn.close()
        return True
    except Exception:
        return False


GOLDEN_READY = os.getenv("RUN_LOCAL_MYSQL_TESTS") == "1" and _dependencies_available()
skip_without_deps = pytest.mark.skipif(
    not GOLDEN_READY,
    reason="OPENAI_API_KEY 또는 로컬 purchase DB(purchase_reader)가 준비되어 있지 않습니다",
)


def _load_golden_cases() -> list[dict]:
    if not CASES_PATH.exists():
        return []
    lines = [
        line
        for line in CASES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [json.loads(line) for line in lines]


@skip_without_deps
@pytest.mark.parametrize("case", _load_golden_cases(), ids=lambda c: c["question"])
def test_golden_case_generates_expected_sql(case: dict) -> None:
    """골든 케이스는 원래 단일 SQL 질문만 다루므로, 복합질문으로 쪼개져도 첫 항목만 본다.

    변경 이유: generate_sql()이 이제 list[dict]를 반환한다(NO_SQL=[]).
    """
    schema = get_schema_resource()
    queries = asyncio.run(text2sql_module.generate_sql(case["question"], schema))

    if case.get("expect_no_sql"):
        assert (
            queries == []
        ), f"'{case['question']}'는 NO_SQL이어야 하는데 SQL이 생성됨: {queries}"
        return

    assert queries, f"'{case['question']}'는 SQL이 생성돼야 하는데 비어 있음"
    sql = queries[0]["sql"]
    normalized = validate_and_normalize(sql)
    used = referenced_tables(normalized)
    for expected_view in case.get("expected_views", []):
        assert (
            expected_view in used
        ), f"'{case['question']}' -> {normalized}\n기대한 뷰 '{expected_view}'가 없음"
    for forbidden in case.get("forbidden_substrings", []):
        assert (
            forbidden not in normalized
        ), f"'{case['question']}' -> {normalized}\n금지된 표현 '{forbidden}'이 포함됨"
