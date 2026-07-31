from __future__ import annotations

from typing import TypedDict


class SchemaResource(TypedDict):
    tables: list[str]
    columns: dict[str, list[str]]
    business_glossary: dict[str, str]


def get_schema_resource() -> SchemaResource:
<<<<<<< HEAD
    """Text2SQL에 판매 테이블·컬럼·업무 용어를 제공하는 MCP Resource를 만든다."""
    return {
        "tables": [
            "customers", "inventory_items", "credit_limits", "customer_contracts",
            "price_lists", "sales_quotes", "stock_levels", "discounts",
            "inventory_transfers", "sales_orders", "sales_quote_lines",
            "order_fulfillment", "sales_order_lines", "fulfillment_lines",
            "invoices", "sales_reports", "sales_forecasts",
        ],
        "columns": {
            "customers": ["customer_id", "customer_code", "customer_name", "customer_type", "industry", "country", "currency", "is_active"],
            "sales_orders": ["sales_order_id", "customer_id", "order_number", "order_date", "subtotal", "discount_amount", "tax_amount", "total_amount", "status"],
            "sales_order_lines": ["sales_order_line_id", "sales_order_id", "item_id", "description", "quantity", "unit_price", "line_total", "quantity_delivered"],
            "invoices": ["invoice_id", "customer_id", "order_id", "invoice_number", "invoice_date", "due_date", "total_amount", "amount_paid", "outstanding_amount", "status"],
            "price_lists": ["price_list_id", "item_id", "list_name", "customer_segment", "is_active"],
            "credit_limits": ["credit_limit_id", "customer_id", "credit_limit_amount", "current_exposure", "available_credit", "credit_rating", "is_on_hold"],
            "stock_levels": ["stock_level_id", "item_id", "warehouse_id", "quantity_on_hand", "quantity_reserved", "quantity_available"],
            "sales_reports": ["sales_report_id", "sales_order_id", "customer_id", "report_type", "period_start", "period_end", "total_revenue", "orders_count"],
        },
        "business_glossary": {
            "매출": "sales_orders.total_amount 합계 또는 invoices.total_amount 합계",
            "고객": "customers 테이블",
            "미수금": "invoices.outstanding_amount",
            "재고": "stock_levels.quantity_available",
            "VIP 고객": "price_lists.customer_segment = 'VIP'",
            "여신한도": "credit_limits.credit_limit_amount",
        },
    }
=======
    """판매 도메인의 View·컬럼·용어를 반환한다."""
    ...
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0
