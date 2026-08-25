"""app/services/anomaly_service.py(3단계) 단위 테스트.

query_readonly를 목으로 대체해 실제 DB 없이, 규칙별 SQL→AnomalyRow 매핑·부분 실패
격리·sql_guard 통과 여부(회귀)를 검증한다.

TEMP: app/services/anomaly_service.py를 지울 때 이 파일도 함께 지운다
(docs/team_share/09_anomaly_temp_dashboard_cleanup.md 참고).
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from unittest import mock

import pytest

from app.services import anomaly_service as svc
from app.services.anomaly_service import get_anomalies


def _dispatch_by_sql_keyword(rows_by_keyword: dict[str, list[dict[str, Any]]]):
    """SQL 문자열에 포함된 키워드로 어느 규칙 호출인지 구분해 고정 결과를 준다.

    실제 3개 규칙 SQL은 서로 겹치지 않는 표식을 하나씩 갖는다: 금액 이상치는
    STDDEV, 연체 과다는 Overdue, 급증거래는 avg_monthly_6m.
    """

    def query(sql: str) -> list[dict[str, Any]]:
        for keyword, rows in rows_by_keyword.items():
            if keyword in sql:
                return rows
        raise AssertionError(f"예상하지 못한 SQL 호출: {sql[:120]}")

    return query


def _sales_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "STDDEV": [
            {
                "entity": "Amman Capital",
                "amount": Decimal("1699885.51"),
                "detail": "SO-1 (2026-01-01)",
            }
        ],
        "Overdue": [
            {"entity": "Petra Steel", "amount": Decimal("566828.31"), "detail": "3건 연체"}
        ],
        "avg_monthly_6m": [
            {
                "entity": "National Cargo",
                "amount": Decimal("18798.63"),
                "detail": "최근30일 18798.63 vs 6개월평균 80.59",
            }
        ],
    }


def _purchase_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "STDDEV": [
            {
                "entity": "Petra Industrial Supplies",
                "amount": Decimal("463598.15"),
                "detail": "PO-1 (2026-01-01)",
            }
        ],
        "Overdue": [
            {"entity": "Cedar Automation", "amount": Decimal("29024.46"), "detail": "2건 연체"}
        ],
        "avg_monthly_6m": [
            {
                "entity": "Cedar Automation",
                "amount": Decimal("3450.21"),
                "detail": "최근30일 3450.21 vs 6개월평균 77.01",
            }
        ],
    }


def test_get_anomalies_maps_rows_into_common_schema() -> None:
    with (
        mock.patch.object(
            svc,
            "query_sales_readonly",
            side_effect=_dispatch_by_sql_keyword(_sales_rows()),
        ),
        mock.patch.object(
            svc,
            "query_purchase_readonly",
            side_effect=_dispatch_by_sql_keyword(_purchase_rows()),
        ),
    ):
        rows = asyncio.run(get_anomalies())

    assert len(rows) == 6
    by_key = {(row["domain"], row["type"]): row for row in rows}
    assert set(by_key) == {
        ("sales", "amount_outlier"),
        ("sales", "overdue"),
        ("sales", "spike"),
        ("purchase", "amount_outlier"),
        ("purchase", "overdue"),
        ("purchase", "spike"),
    }

    outlier = by_key[("sales", "amount_outlier")]
    assert outlier["entity"] == "Amman Capital"
    assert outlier["amount"] == 1699885.51
    assert isinstance(outlier["amount"], float)  # Decimal -> float 변환 확인
    assert outlier["detail"] == "SO-1 (2026-01-01)"


def test_get_anomalies_uses_one_shared_detected_at_per_call() -> None:
    with (
        mock.patch.object(
            svc,
            "query_sales_readonly",
            side_effect=_dispatch_by_sql_keyword(_sales_rows()),
        ),
        mock.patch.object(
            svc,
            "query_purchase_readonly",
            side_effect=_dispatch_by_sql_keyword(_purchase_rows()),
        ),
    ):
        rows = asyncio.run(get_anomalies())

    assert len({row["detected_at"] for row in rows}) == 1


def test_get_anomalies_calls_correct_client_per_domain() -> None:
    with (
        mock.patch.object(
            svc,
            "query_sales_readonly",
            side_effect=_dispatch_by_sql_keyword(_sales_rows()),
        ) as mock_sales,
        mock.patch.object(
            svc,
            "query_purchase_readonly",
            side_effect=_dispatch_by_sql_keyword(_purchase_rows()),
        ) as mock_purchase,
    ):
        asyncio.run(get_anomalies())

    assert mock_sales.call_count == 3
    assert mock_purchase.call_count == 3


def test_get_anomalies_isolates_one_rule_failure_from_the_rest() -> None:
    """한 도메인의 query_readonly가 통째로 실패해도 나머지 도메인 결과는 살아남는다."""

    def failing_sales(sql: str) -> list[dict[str, Any]]:
        raise RuntimeError("연결 실패 시뮬레이션")

    with (
        mock.patch.object(svc, "query_sales_readonly", side_effect=failing_sales),
        mock.patch.object(
            svc,
            "query_purchase_readonly",
            side_effect=_dispatch_by_sql_keyword(_purchase_rows()),
        ),
    ):
        rows = asyncio.run(get_anomalies())

    assert len(rows) == 3
    assert {row["domain"] for row in rows} == {"purchase"}


def test_get_anomalies_returns_empty_list_when_nothing_is_anomalous() -> None:
    empty: dict[str, list[dict[str, Any]]] = {
        "STDDEV": [],
        "Overdue": [],
        "avg_monthly_6m": [],
    }
    with (
        mock.patch.object(
            svc, "query_sales_readonly", side_effect=_dispatch_by_sql_keyword(empty)
        ),
        mock.patch.object(
            svc, "query_purchase_readonly", side_effect=_dispatch_by_sql_keyword(empty)
        ),
    ):
        rows = asyncio.run(get_anomalies())

    assert rows == []


# ---------------------------------------------------------------------------
# 회귀 테스트: 3단계에서 CTE(WITH)가 sql_guard에 거부당했던 문제를 다시 잡는다.
# query_readonly()는 호출자와 무관하게 항상 sql_guard.validate_and_normalize()를
# 거치므로, 이 6개 고정 SQL도 실제로 그 검사를 통과해야 한다.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql_name",
    ["_SALES_AMOUNT_OUTLIER_SQL", "_SALES_OVERDUE_SQL", "_SALES_SPIKE_SQL"],
)
def test_sales_sql_passes_sql_guard_and_stays_within_sales_views(sql_name: str) -> None:
    from mcp_servers.data_tools.sales.sql_guard import validate_and_normalize

    sql = getattr(svc, sql_name)
    validate_and_normalize(sql)  # ValueError를 내면 실패
    assert "v_purchase_order" not in sql
    assert "v_vendor_invoice" not in sql


@pytest.mark.parametrize(
    "sql_name",
    ["_PURCHASE_AMOUNT_OUTLIER_SQL", "_PURCHASE_OVERDUE_SQL", "_PURCHASE_SPIKE_SQL"],
)
def test_purchase_sql_passes_sql_guard_and_stays_within_purchase_views(
    sql_name: str,
) -> None:
    from mcp_servers.data_tools.purchase.sql_guard import validate_and_normalize

    sql = getattr(svc, sql_name)
    validate_and_normalize(sql)  # ValueError를 내면 실패
    assert "v_sales_order" not in sql
    assert "v_invoice" not in sql
