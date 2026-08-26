"""고정 SQL 3종 x 2도메인(sales/purchase)의 이상탐지 결과를 하나의 리스트로 모은다.

LLM/Text2SQL을 전혀 거치지 않는다 — 질문마다 SQL을 새로 생성하는 게 아니라 2단계에서
sales_reader/purchase_reader로 직접 검증한 고정 SQL만 그대로 실행한다.

# old: "LLM이 만든 SQL을 검사하는 sql_guard가 필요 없다"
# 정정: query_readonly()는 호출자가 누구든 항상 sql_guard.validate_and_normalize()를
# 거친다(mcp_servers/data_tools/sales/mysql.py:29) — 우회할 방법이 없는, 이
# 프로젝트의 유일한 읽기 경로에 박힌 방어선이다. 이 파일의 SQL도 실제로 그 검사를
# 통과해야 하며, 그래서 CTE(WITH)를 못 쓰고 서브쿼리로 다시 썼다(아래 _SALES_SPIKE_SQL
# 주석 참고 — 가드가 CTE 별칭을 허용 목록 밖 테이블로 오인해서 거부했다).

"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal

# 추가: response_model로 그대로 노출하려면(app/api/anomalies.py) typing.TypedDict가
# 아니라 typing_extensions.TypedDict가 필요하다 — Python 3.11 + pydantic v2에서는
# typing.TypedDict를 pydantic이 스키마로 못 만든다(직접 재현해서 확인함:
# "Please use `typing_extensions.TypedDict` instead of `typing.TypedDict` on
# Python < 3.12"). mcp_servers/data_tools/*/schema.py의 TypedDict들은 API 응답으로
# 안 나가서 이 문제가 없었다.
from typing_extensions import TypedDict

from mcp_servers.data_tools.purchase.mysql import (
    query_readonly as query_purchase_readonly,
)
from mcp_servers.data_tools.sales.mysql import query_readonly as query_sales_readonly

logger = logging.getLogger(__name__)

AnomalyDomain = Literal["sales", "purchase"]
AnomalyType = Literal["amount_outlier", "overdue", "spike"]


class AnomalyRow(TypedDict):
    """이상탐지 결과 한 행. 도메인·유형이 달라도 항상 같은 모양이라 프론트에서
    하나의 표로 그릴 수 있다.
    """

    domain: AnomalyDomain
    type: AnomalyType
    entity: str
    amount: float
    detail: str
    detected_at: str


# ---------------------------------------------------------------------------
# 2단계에서 sales_reader/purchase_reader로 직접 실행해 결과 건수·값을 확인하고
# 임계값을 조정한 고정 SQL. entity/amount/detail 별칭으로 AnomalyRow와 컬럼을
# 맞춰뒀다.
# ---------------------------------------------------------------------------

_SALES_AMOUNT_OUTLIER_SQL = """
    SELECT customer_name AS entity, order_amount AS amount,
           CONCAT(order_number, ' (', order_date, ')') AS detail
    FROM v_sales_order
    WHERE order_amount > (SELECT AVG(order_amount) + 3*STDDEV(order_amount) FROM v_sales_order)
       OR order_amount < (SELECT AVG(order_amount) - 3*STDDEV(order_amount) FROM v_sales_order)
    ORDER BY order_amount DESC
    LIMIT 20
"""

_SALES_OVERDUE_SQL = """
    SELECT customer_name AS entity, SUM(outstanding_amount) AS amount,
           CONCAT(COUNT(*), '건 연체') AS detail
    FROM v_invoice
    WHERE status = 'Overdue'
    GROUP BY customer_name
    ORDER BY amount DESC
    LIMIT 10
"""

# baseline(6개월 월평균)이 0인 거래처까지 포함하면(LEFT JOIN + COALESCE) "6개월간
# 주문 0건이던 거래처의 첫 소액 주문"까지 급증으로 잡히는 노이즈가 대부분을
# 차지했다(2단계에서 실측). baseline > 0을 요구하는 INNER JOIN으로 바꿔
# "이력이 있는 거래처의 진짜 증가"만 남겼다.
#
# old(2단계 초안, CTE 사용):
#   WITH ref AS (SELECT MAX(order_date) AS as_of FROM v_sales_order),
#   recent AS (... FROM v_sales_order, ref ...), baseline AS (... FROM v_sales_order, ref ...)
#   SELECT ... FROM recent r JOIN baseline b ON ...
# 변경 이유: query_readonly()가 항상 sql_guard.validate_and_normalize()를 거치는데
# (mcp_servers/data_tools/sales/mysql.py:29), 이 가드는 FROM/JOIN 뒤 식별자를 전부
# "테이블 참조"로 보는 단순 정규식이라 CTE 별칭 recent/baseline까지 허용 목록 밖
# 테이블로 오인해 거부한다("허용되지 않은 테이블/뷰를 참조합니다: baseline, recent",
# 실제로 재현해서 확인함). CTE 대신 괄호로 감싼 서브쿼리(파생 테이블)로 바꾸면
# 별칭이 FROM/JOIN 뒤에 괄호로 시작해 이 정규식에 안 걸린다.
_SALES_SPIKE_SQL = """
    SELECT r.entity AS entity, r.recent_30d_total AS amount,
           CONCAT('최근30일 ', r.recent_30d_total, ' vs 6개월평균 ', ROUND(b.avg_monthly_6m, 2)) AS detail
    FROM (
        SELECT customer_name AS entity, SUM(order_amount) AS recent_30d_total
        FROM v_sales_order
        WHERE order_date > DATE_SUB((SELECT MAX(order_date) FROM v_sales_order), INTERVAL 30 DAY)
        GROUP BY customer_name
    ) AS r
    JOIN (
        SELECT customer_name AS entity, SUM(order_amount) / 6 AS avg_monthly_6m
        FROM v_sales_order
        WHERE order_date <= DATE_SUB((SELECT MAX(order_date) FROM v_sales_order), INTERVAL 30 DAY)
          AND order_date > DATE_SUB((SELECT MAX(order_date) FROM v_sales_order), INTERVAL 210 DAY)
        GROUP BY customer_name
    ) AS b ON r.entity = b.entity
    WHERE b.avg_monthly_6m > 0
      AND r.recent_30d_total > 3 * b.avg_monthly_6m
    ORDER BY r.recent_30d_total DESC
    LIMIT 20
"""

_PURCHASE_AMOUNT_OUTLIER_SQL = """
    SELECT vendor_name AS entity, po_amount AS amount,
           CONCAT(po_number, ' (', po_date, ')') AS detail
    FROM v_purchase_order
    WHERE po_amount > (SELECT AVG(po_amount) + 3*STDDEV(po_amount) FROM v_purchase_order)
       OR po_amount < (SELECT AVG(po_amount) - 3*STDDEV(po_amount) FROM v_purchase_order)
    ORDER BY po_amount DESC
    LIMIT 20
"""

_PURCHASE_OVERDUE_SQL = """
    SELECT vendor_name AS entity, SUM(outstanding_amount) AS amount,
           CONCAT(COUNT(*), '건 연체') AS detail
    FROM v_vendor_invoice
    WHERE status = 'Overdue'
    GROUP BY vendor_name
    ORDER BY amount DESC
    LIMIT 10
"""

# sales 급증거래와 동일한 이유로 CTE 대신 파생 테이블(서브쿼리) 방식을 쓴다.
_PURCHASE_SPIKE_SQL = """
    SELECT r.entity AS entity, r.recent_30d_total AS amount,
           CONCAT('최근30일 ', r.recent_30d_total, ' vs 6개월평균 ', ROUND(b.avg_monthly_6m, 2)) AS detail
    FROM (
        SELECT vendor_name AS entity, SUM(po_amount) AS recent_30d_total
        FROM v_purchase_order
        WHERE po_date > DATE_SUB((SELECT MAX(po_date) FROM v_purchase_order), INTERVAL 30 DAY)
        GROUP BY vendor_name
    ) AS r
    JOIN (
        SELECT vendor_name AS entity, SUM(po_amount) / 6 AS avg_monthly_6m
        FROM v_purchase_order
        WHERE po_date <= DATE_SUB((SELECT MAX(po_date) FROM v_purchase_order), INTERVAL 30 DAY)
          AND po_date > DATE_SUB((SELECT MAX(po_date) FROM v_purchase_order), INTERVAL 210 DAY)
        GROUP BY vendor_name
    ) AS b ON r.entity = b.entity
    WHERE b.avg_monthly_6m > 0
      AND r.recent_30d_total > 3 * b.avg_monthly_6m
    ORDER BY r.recent_30d_total DESC
    LIMIT 20
"""

QueryFn = Callable[[str], list[dict[str, Any]]]

# 추가: 이 tuple에 query_sales_readonly/query_purchase_readonly 함수 객체를 직접
# 담지 않는다 — 담으면 import 시점 값이 그대로 굳어버려서, 테스트에서
# mock.patch.object(anomaly_service, "query_sales_readonly", fake)로 목킹해도
# 이미 만들어진 _RULES 안의 참조에는 반영되지 않는다(실제로 겪은 문제: 3단계에서
# 이 목킹이 안 먹혀서 _RULES를 직접 수정해 우회해야 했다). 대신 domain 문자열만
# 저장해두고, _run_rule()이 매번 도메인별 함수를 "이름으로" 참조해서 파이썬이
# 호출 시점에 모듈 전역에서 다시 찾아오게 한다 — 이러면 mock.patch.object가
# 정상적으로 먹힌다.
_RULES: list[tuple[AnomalyDomain, AnomalyType, str]] = [
    ("sales", "amount_outlier", _SALES_AMOUNT_OUTLIER_SQL),
    ("sales", "overdue", _SALES_OVERDUE_SQL),
    ("sales", "spike", _SALES_SPIKE_SQL),
    ("purchase", "amount_outlier", _PURCHASE_AMOUNT_OUTLIER_SQL),
    ("purchase", "overdue", _PURCHASE_OVERDUE_SQL),
    ("purchase", "spike", _PURCHASE_SPIKE_SQL),
]


def _query_fn_for_domain(domain: AnomalyDomain) -> QueryFn:
    """도메인에 맞는 query_readonly를 모듈 전역 이름으로 조회한다(위 주석 참고)."""
    return query_sales_readonly if domain == "sales" else query_purchase_readonly


async def _run_rule(
    domain: AnomalyDomain,
    anomaly_type: AnomalyType,
    sql: str,
    detected_at: str,
) -> list[AnomalyRow]:
    """규칙 하나를 실행해 공통 AnomalyRow 모양으로 변환한다.

    query_readonly()는 동기 함수라(sales/purchase mysql.py), 이벤트 루프를 막지
    않도록 to_thread로 감싼다(mcp_servers/data_tools/*/query.py와 동일 패턴).
    """
    query_fn = _query_fn_for_domain(domain)
    rows = await asyncio.to_thread(query_fn, sql)
    return [
        {
            "domain": domain,
            "type": anomaly_type,
            "entity": str(row["entity"]),
            "amount": float(row["amount"]),
            "detail": str(row["detail"]),
            "detected_at": detected_at,
        }
        for row in rows
    ]


async def get_anomalies() -> list[AnomalyRow]:
    """6개 고정 규칙을 병렬로 실행해 하나의 리스트로 합친다.

    한 규칙이 실패해도(예: 한쪽 도메인 DB만 일시적으로 응답이 없음) 나머지 규칙
    결과는 그대로 반환한다 — 임시 대시보드 위젯 하나가 전체 채팅 페이지 로딩을
    막으면 안 되기 때문이다.
    """
    detected_at = datetime.now(timezone.utc).isoformat()
    outcomes = await asyncio.gather(
        *(
            _run_rule(domain, anomaly_type, sql, detected_at)
            for domain, anomaly_type, sql in _RULES
        ),
        return_exceptions=True,
    )

    anomalies: list[AnomalyRow] = []
    for (domain, anomaly_type, _sql), outcome in zip(_RULES, outcomes):
        if isinstance(outcome, BaseException):
            logger.warning(
                "anomaly_rule_failed domain=%s type=%s error=%s",
                domain,
                anomaly_type,
                outcome,
            )
            continue
        anomalies.extend(outcome)
    return anomalies
