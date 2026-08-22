"""판매 Text2SQL(스키마·가드·EXPLAIN 재시도·프롬프트 결과)의 단위/골든 케이스 테스트.

빠른 테스트(스키마 정합성, 가드 규칙, 재시도 흐름)는 외부 서비스 없이 항상 돈다.
골든 케이스(tests/fixtures/cases/text2sql_cases.jsonl)는 실제 OpenAI 호출과
sales_reader/EXPLAIN용 로컬 MySQL이 필요해 tests/unit/test_agent.py와 동일한
RUN_LOCAL_MYSQL_TESTS=1 opt-in 패턴으로만 실행한다(AGENTS.md: 단위 테스트는
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

from mcp_servers.data_tools.sales import query as query_module
from mcp_servers.data_tools.sales import text2sql as text2sql_module
from mcp_servers.data_tools.sales.schema import get_schema_resource
from mcp_servers.data_tools.sales.sql_guard import ALLOWED_VIEWS, referenced_tables, validate_and_normalize

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
CASES_PATH = FIXTURES_DIR / "cases" / "text2sql_cases.jsonl"

# schema.py가 없애기로 한 유령 테이블(SPEC.md 발견 사항). 이 이름들이 스키마
# 리소스 어디에도 다시 나타나면 안 된다.
_PHANTOM_TABLES = ("inventory_items", "stock_levels", "inventory_transfers")


# ---------------------------------------------------------------------------
# 1. 스키마 정합성 (외부 서비스 없음)
# ---------------------------------------------------------------------------


def test_schema_only_advertises_allowed_views() -> None:
    """schema.py의 views 키가 sql_guard의 화이트리스트와 정확히 일치해야 한다."""
    schema = get_schema_resource()
    assert set(schema["views"].keys()) == set(ALLOWED_VIEWS)


def test_schema_has_no_phantom_tables() -> None:
    """제거하기로 한 유령 테이블이 뷰·지표·범위 밖 목록 어디에도 없어야 한다."""
    schema = get_schema_resource()
    haystack = json.dumps(schema, default=str, ensure_ascii=False)
    for phantom in _PHANTOM_TABLES:
        assert phantom not in haystack, f"유령 테이블 '{phantom}'이 스키마 리소스에 남아있습니다."


def test_schema_metrics_reference_allowed_views_only() -> None:
    """지표 정의가 가리키는 뷰도 전부 허용 목록 안에 있어야 한다."""
    schema = get_schema_resource()
    for term, metric in schema["metrics"].items():
        assert metric["view"] in ALLOWED_VIEWS, f"지표 '{term}'이 허용되지 않은 뷰 '{metric['view']}'를 가리킵니다."


def test_revenue_metric_is_defined_once_without_or() -> None:
    """'매출' 지표 설명에 '또는'이 없어야 한다(정의를 하나로 고정한다는 D-16 취지)."""
    schema = get_schema_resource()
    metric = schema["metrics"]["매출"]
    assert metric["view"] == "v_sales_order"
    assert metric["column"] == "order_amount"
    assert "또는" not in metric["note"]


def test_fallback_templates_removed() -> None:
    """API 키가 없을 때 질문과 무관한 SQL을 돌려주던 하드코딩이 없어야 한다."""
    for name in ("_FALLBACK_TEMPLATES", "_DEFAULT_FALLBACK_SQL", "_generate_sql_fallback"):
        assert not hasattr(text2sql_module, name), f"{name}이(가) 아직 남아있습니다."


def test_generate_sql_raises_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """API 키가 없으면 조용히 폴백하지 않고 예외를 낸다(server.py가 QUERY_ERROR로 변환)."""
    fake_settings = mock.Mock(openai_api_key="")
    monkeypatch.setattr(text2sql_module, "get_settings", lambda: fake_settings)

    with pytest.raises(RuntimeError):
        asyncio.run(text2sql_module.generate_sql("아무 질문", get_schema_resource()))


# ---------------------------------------------------------------------------
# 2. SQL 가드 (외부 서비스 없음)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; SELECT 2",
        "UPDATE v_sales_order SET status='x'",
        "SELECT /* bypass */ 1 FROM v_sales_order",
        "SELECT * FROM sales_orders",  # 원본 테이블 — 화이트리스트 밖
        "SELECT * FROM v_sales_order INTO OUTFILE '/tmp/x.csv'",
    ],
)
def test_guard_rejects_unsafe_sql(sql: str) -> None:
    with pytest.raises(ValueError):
        validate_and_normalize(sql)


def test_guard_appends_default_limit_when_missing() -> None:
    result = validate_and_normalize("SELECT customer_id FROM v_sales_order")
    assert "LIMIT 200" in result


def test_guard_caps_limit_above_maximum() -> None:
    result = validate_and_normalize("SELECT customer_id FROM v_sales_order LIMIT 5000")
    assert "LIMIT 200" in result
    assert "5000" not in result


def test_guard_keeps_limit_within_maximum() -> None:
    result = validate_and_normalize("SELECT customer_id FROM v_sales_order LIMIT 10")
    assert "LIMIT 10" in result


def test_referenced_tables_finds_multiple_joins() -> None:
    sql = "SELECT a.x FROM v_sales_order a JOIN v_invoice b ON a.customer_id = b.customer_id"
    assert referenced_tables(sql) == {"v_sales_order", "v_invoice"}


# ---------------------------------------------------------------------------
# 3. 파이프라인 재시도 흐름 (LLM/DB를 mock으로 대체 — 외부 서비스 없음)
# ---------------------------------------------------------------------------


def test_query_sales_returns_empty_when_llm_declines() -> None:
    """LLM이 NO_SQL로 답하면(범위 밖) rows=[]를 돌려줘 server.py가 NO_RESULT로 처리한다."""

    async def declines(question: str, schema: Any) -> str:
        return ""

    with mock.patch.object(query_module, "generate_sql", declines):
        evidence = asyncio.run(query_module.query_sales("답할 수 없는 질문"))

    assert evidence[0]["rows"] == []
    assert evidence[0]["domain"] == "sales"
    assert evidence[0]["metadata"]["retry_count"] == 0


def test_query_sales_returns_empty_for_blank_question() -> None:
    evidence = asyncio.run(query_module.query_sales("   "))
    assert evidence[0]["rows"] == []


def test_query_sales_returns_empty_for_too_long_question() -> None:
    evidence = asyncio.run(query_module.query_sales("가" * 501))
    assert evidence[0]["rows"] == []


def test_query_sales_retries_once_on_explain_failure() -> None:
    """EXPLAIN이 실패하면 오류 메시지를 재작성 함수에 넘기고 최대 1회만 재시도한다."""
    calls: list[str] = []

    async def first_sql(question: str, schema: Any) -> str:
        return "SELECT bad_column FROM v_sales_order LIMIT 5"

    async def retried_sql(question: str, schema: Any, failed_sql: str, error: str) -> str:
        calls.append(error)
        return "SELECT customer_id FROM v_sales_order LIMIT 5"

    def fake_explain(sql: str) -> None:
        if "bad_column" in sql:
            raise RuntimeError("Unknown column 'bad_column'")

    def fake_query_readonly(sql: str) -> list[dict[str, Any]]:
        return [{"customer_id": 1}]

    with mock.patch.object(query_module, "generate_sql", first_sql), \
         mock.patch.object(query_module, "generate_sql_with_error", retried_sql), \
         mock.patch.object(query_module, "explain_readonly", fake_explain), \
         mock.patch.object(query_module, "query_readonly", fake_query_readonly):
        evidence = asyncio.run(query_module.query_sales("아무 질문"))

    assert len(calls) == 1
    assert "bad_column" in calls[0]
    assert evidence[0]["metadata"]["retry_count"] == 1
    assert evidence[0]["row_count"] == 1


def test_query_sales_raises_when_retry_also_fails() -> None:
    """재시도까지 실패하면 예외를 그대로 올려 server.py가 QUERY_ERROR로 변환하게 한다."""

    async def first_sql(question: str, schema: Any) -> str:
        return "SELECT bad_column FROM v_sales_order LIMIT 5"

    async def retried_sql(question: str, schema: Any, failed_sql: str, error: str) -> str:
        return "SELECT still_bad FROM v_sales_order LIMIT 5"

    def fake_explain(sql: str) -> None:
        raise RuntimeError("always fails")

    with mock.patch.object(query_module, "generate_sql", first_sql), \
         mock.patch.object(query_module, "generate_sql_with_error", retried_sql), \
         mock.patch.object(query_module, "explain_readonly", fake_explain):
        with pytest.raises(RuntimeError):
            asyncio.run(query_module.query_sales("아무 질문"))


def test_chart_hint_prefers_line_for_period_columns() -> None:
    assert query_module._chart_hint([{"order_month": "2026-01", "total": 1}]) == "line"
    assert query_module._chart_hint([{"customer_name": "A", "total": 1}]) == "bar"
    assert query_module._chart_hint([]) is None


# ---------------------------------------------------------------------------
# 4. 골든 케이스 — 실제 OpenAI + 로컬 sales DB 필요 (opt-in)
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
            host=settings.mysql_read_host,
            user=settings.sales_read_user or settings.mysql_read_user,
            password=settings.sales_read_password or settings.mysql_read_password,
            database=settings.sales_db_database,
        )
        conn.close()
        return True
    except Exception:
        return False


GOLDEN_READY = os.getenv("RUN_LOCAL_MYSQL_TESTS") == "1" and _dependencies_available()
skip_without_deps = pytest.mark.skipif(
    not GOLDEN_READY,
    reason="OPENAI_API_KEY 또는 로컬 sales DB(sales_reader)가 준비되어 있지 않습니다",
)


def _load_golden_cases() -> list[dict]:
    if not CASES_PATH.exists():
        return []
    lines = [line for line in CASES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


@skip_without_deps
@pytest.mark.parametrize("case", _load_golden_cases(), ids=lambda c: c["question"])
def test_golden_case_generates_expected_sql(case: dict) -> None:
    schema = get_schema_resource()
    sql = asyncio.run(text2sql_module.generate_sql(case["question"], schema))

    if case.get("expect_no_sql"):
        assert sql == "", f"'{case['question']}'는 NO_SQL이어야 하는데 SQL이 생성됨: {sql}"
        return

    assert sql, f"'{case['question']}'는 SQL이 생성돼야 하는데 비어 있음"
    normalized = validate_and_normalize(sql)
    used = referenced_tables(normalized)
    for expected_view in case.get("expected_views", []):
        assert expected_view in used, f"'{case['question']}' -> {normalized}\n기대한 뷰 '{expected_view}'가 없음"
    for forbidden in case.get("forbidden_substrings", []):
        assert forbidden not in normalized, f"'{case['question']}' -> {normalized}\n금지된 표현 '{forbidden}'이 포함됨"
