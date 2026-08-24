"""판매 Text2SQL에 허용된 뷰·지표·업무 용어 Resource.

LLM에게는 원본 테이블이 아니라 database/sales/views.sql의 뷰 5개만 알려준다.
"매출이 뭔지" 같은 업무 정의를 LLM이 그때그때 판단하지 않도록, 지표(metric)마다
어느 뷰·어느 컬럼·어떤 집계 함수를 쓸지 여기서 못박아둔다(SPEC.md 4·7절 참고).
"""

from __future__ import annotations

from typing import TypedDict

from mcp_servers.data_tools.sales.mysql import query_readonly


class ViewSpec(TypedDict):
    """LLM에게 노출하는 뷰 1개의 설명과 사용 가능한 컬럼."""

    description: str
    columns: list[str]


class MetricSpec(TypedDict):
    """업무 용어 1개가 어느 뷰·컬럼·집계로 고정되는지."""

    view: str
    column: str
    aggregation: str
    note: str


class SchemaResource(TypedDict):
    """판매 Text2SQL이 사용할 뷰·지표·범위 정보."""

    views: dict[str, ViewSpec]
    metrics: dict[str, MetricSpec]
    out_of_scope: list[str]
    data_coverage: dict[str, str]
    currency: str


_VIEWS: dict[str, ViewSpec] = {
    "v_sales_order": {
        "description": "유효한 주문 헤더 1건당 1행. 취소(Cancelled)·초안(Draft) 상태는 이미 제외되어 있다.",
        "columns": [
            "sales_order_id",
            "order_number",
            "order_date",
            "order_year",
            "order_quarter",
            "order_month",
            "customer_id",
            "customer_name",
            "customer_type",
            "industry",
            "country",
            "status",
            "currency",
            "subtotal",
            "discount_amount",
            "tax_amount",
            "order_amount",
            "required_delivery_date",
            "payment_terms",
        ],
    },
    "v_sales_order_line": {
        "description": (
            "유효한 주문의 라인(상세) 1건당 1행. 주문 헤더 금액 컬럼은 없다 — "
            "품목별 집계는 반드시 이 뷰의 line_total만 SUM한다. v_sales_order의 "
            "order_amount와 절대 합치지 마라(라인 수만큼 중복 합산된다)."
        ),
        "columns": [
            "sales_order_line_id",
            "sales_order_id",
            "order_number",
            "order_date",
            "order_year",
            "order_quarter",
            "order_month",
            "customer_id",
            "customer_name",
            "industry",
            "country",
            "item_id",
            "item_name",
            "quantity",
            "unit_price",
            "discount_percent",
            "line_total",
            "quantity_delivered",
            "currency",
            "status",
        ],
    },
    "v_invoice": {
        "description": "청구서 1건당 1행. 미수금(outstanding_amount)과 연체 여부(status)를 담는다.",
        "columns": [
            "invoice_id",
            "invoice_number",
            "invoice_date",
            "due_date",
            "invoice_year",
            "invoice_quarter",
            "invoice_month",
            "customer_id",
            "customer_name",
            "customer_type",
            "country",
            "order_id",
            "subtotal",
            "tax_amount",
            "invoice_amount",
            "amount_paid",
            "outstanding_amount",
            "currency",
            "status",
            "payment_terms",
        ],
    },
    "v_customer": {
        "description": (
            "고객 마스터 1건당 1행. 이메일·전화번호·주소·세금ID 같은 개인정보 컬럼은 "
            "이 뷰에 아예 없다 — 그런 정보는 조회할 수 없다고 답하라."
        ),
        "columns": [
            "customer_id",
            "customer_code",
            "customer_name",
            "customer_type",
            "industry",
            "country",
            "currency",
            "payment_terms",
            "is_active",
            "created_at",
        ],
    },
    "v_sales_order_status": {
        "description": (
            "상태(취소·초안 포함) x 월 단위로 미리 집계된 표. '취소된 주문이 몇 건이야' "
            "같이 취소·초안까지 포함해서 세는 질문에만 쓴다. 매출 지표에는 쓰지 마라 "
            "(취소분이 섞여 들어간다)."
        ),
        "columns": ["status", "currency", "order_month", "order_count", "total_amount"],
    },
}

_METRICS: dict[str, MetricSpec] = {
    "매출": {
        "view": "v_sales_order",
        "column": "order_amount",
        "aggregation": "SUM",
        "note": "뷰가 이미 취소·초안 제외. '수주액'과 같은 뜻이다.",
    },
    "수주액": {
        "view": "v_sales_order",
        "column": "order_amount",
        "aggregation": "SUM",
        "note": "뷰가 이미 취소·초안 제외.",
    },
    "주문 건수": {
        "view": "v_sales_order",
        "column": "sales_order_id",
        "aggregation": "COUNT",
        "note": "뷰가 이미 취소·초안 제외.",
    },
    "품목별 매출": {
        "view": "v_sales_order_line",
        "column": "line_total",
        "aggregation": "SUM",
        "note": "item_name으로 GROUP BY. v_sales_order의 order_amount를 쓰면 안 된다(중복 합산).",
    },
    "판매 수량": {
        "view": "v_sales_order_line",
        "column": "quantity",
        "aggregation": "SUM",
        "note": "",
    },
    "청구액": {
        "view": "v_invoice",
        "column": "invoice_amount",
        "aggregation": "SUM",
        "note": "",
    },
    "미수금": {
        "view": "v_invoice",
        "column": "outstanding_amount",
        "aggregation": "SUM",
        "note": "",
    },
    "연체 미수금": {
        "view": "v_invoice",
        "column": "outstanding_amount",
        "aggregation": "SUM",
        "note": "WHERE status = 'Overdue' 조건을 반드시 붙인다.",
    },
    "취소 주문 현황": {
        "view": "v_sales_order_status",
        "column": "order_count",
        "aggregation": "SUM",
        "note": "매출 지표가 아니라 상태 현황용. status='Cancelled' 조건과 함께 쓴다.",
    },
}

# 데이터가 없거나 뷰로 답할 수 없는 지표. 왜 안 되는지 사용자에게 설명할 때 쓴다.
_OUT_OF_SCOPE: list[str] = [
    "영업이익",
    "매출총이익",
    "원가",
    "마진율",
    "재고",
    "재고회전율",
    "구매",
    "발주",
    "공급업체",
    "미지급금",
    "견적",
    "출하",
    "배송",
    "여신한도",
    "할인정책",
    "매출예측",
    "공급업체평가",
]

_CURRENCY = "JOD"

_cached_data_coverage: dict[str, str] | None = None


def _load_data_coverage() -> dict[str, str]:
    """v_sales_order의 실제 주문 날짜 범위를 1회 조회해 이후 재사용한다.

    매 질문마다 조회하면 불필요한 DB 왕복이 생기므로 프로세스 수명 동안 캐시한다.
    ETL로 데이터를 다시 채운 뒤에는 프로세스를 재시작해야 갱신된다.
    """
    global _cached_data_coverage
    if _cached_data_coverage is not None:
        return _cached_data_coverage

    try:
        rows = query_readonly(
            "SELECT MIN(order_date) AS min_d, MAX(order_date) AS max_d FROM v_sales_order"
        )
    except (
        Exception
    ):  # noqa: BLE001 - DB 미가용 시에도 스키마 정보 자체는 내려줄 수 있어야 한다.
        rows = []

    if rows and rows[0].get("min_d") and rows[0].get("max_d"):
        _cached_data_coverage = {
            "min_order_date": str(rows[0]["min_d"]),
            "max_order_date": str(rows[0]["max_d"]),
        }
    else:
        _cached_data_coverage = {"min_order_date": "", "max_order_date": ""}
    return _cached_data_coverage


def get_schema_resource() -> SchemaResource:
    """Text2SQL에 판매 뷰·지표·데이터 범위를 제공하는 MCP Resource를 만든다."""
    return {
        "views": _VIEWS,
        "metrics": _METRICS,
        "out_of_scope": _OUT_OF_SCOPE,
        "data_coverage": _load_data_coverage(),
        "currency": _CURRENCY,
    }
