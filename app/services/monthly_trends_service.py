# -*- coding: utf-8 -*-
"""대시보드 차트용 - 올해 월별 구매/매출 추이 고정 SQL API.

`app/services/anomaly_service.py`와 완전히 동일한 설계 원칙을 따른다:
    - LLM/Text2SQL을 전혀 거치지 않는다. 질문마다 SQL을 새로 생성하지 않고,
      sales_reader/purchase_reader로 검증한 고정 SQL만 그대로 실행한다.
    - query_readonly()는 항상 sql_guard.validate_and_normalize()를 거치므로
      (mcp_servers/data_tools/*/mysql.py), 여기서 만드는 SQL도 허용된 뷰만
      참조하는 단일 SELECT여야 한다 - CTE(WITH) 대신 파생 테이블(서브쿼리)도
      필요 없을 만큼 단순한 GROUP BY라 문제없다.
    - 한쪽 도메인(sales/purchase) 조회가 실패해도 다른 쪽은 정상 반환되도록
      asyncio.gather(..., return_exceptions=True)로 격리한다.

이 파일을 app/services/ 에 새로 추가하기만 하면 되고, 기존 파일은 손대지 않는다.
"""

from __future__ import annotations

import asyncio
from typing import Any

from typing_extensions import TypedDict

from mcp_servers.data_tools.purchase.mysql import (
    query_readonly as query_purchase_readonly,
)
from mcp_servers.data_tools.sales.mysql import query_readonly as query_sales_readonly


class MonthlyTrendPoint(TypedDict):
    """월 하나의 합계. month는 'YYYY-MM' 형식이라 프론트에서 그대로 x축 라벨로
    쓸 수 있다."""

    month: str
    amount: float


class MonthlyTrends(TypedDict):
    sales: list[MonthlyTrendPoint]
    purchase: list[MonthlyTrendPoint]


def _sales_monthly_sql(year: int) -> str:
    # year는 라우터에서 FastAPI가 int로 타입 검증한 값만 여기 들어오므로
    # (app/api/dashboard.py 참고) f-string으로 끼워도 SQL 인젝션 여지가 없다.
    return f"""
        SELECT DATE_FORMAT(order_date, '%Y-%m') AS month, SUM(order_amount) AS amount
        FROM v_sales_order
        WHERE YEAR(order_date) = {year}
        GROUP BY DATE_FORMAT(order_date, '%Y-%m')
        ORDER BY month
    """


def _purchase_monthly_sql(year: int) -> str:
    return f"""
        SELECT DATE_FORMAT(po_date, '%Y-%m') AS month, SUM(po_amount) AS amount
        FROM v_purchase_order
        WHERE YEAR(po_date) = {year}
        GROUP BY DATE_FORMAT(po_date, '%Y-%m')
        ORDER BY month
    """


async def _monthly(query_fn: Any, sql: str) -> list[MonthlyTrendPoint]:
    rows = await asyncio.to_thread(query_fn, sql)
    return [
        {"month": str(row["month"]), "amount": float(row["amount"])} for row in rows
    ]


async def get_monthly_trends(year: int) -> MonthlyTrends:
    """지정한 연도의 sales/purchase 월별 합계를 병렬로 조회한다.

    데이터가 없는 달은 결과에 아예 나오지 않는다(0으로 채워 12개를 다 만들지
    않음) - 차트 라이브러리에서 x축을 라벨 배열로 직접 관리하는 편이 보통 더
    유연해서, 빈 달 채우기는 필요하면 프론트에서 처리하는 쪽을 권장한다.
    """
    sales_result, purchase_result = await asyncio.gather(
        _monthly(query_sales_readonly, _sales_monthly_sql(year)),
        _monthly(query_purchase_readonly, _purchase_monthly_sql(year)),
        return_exceptions=True,
    )
    sales = sales_result if not isinstance(sales_result, BaseException) else []
    purchase = purchase_result if not isinstance(purchase_result, BaseException) else []
    return {"sales": sales, "purchase": purchase}
