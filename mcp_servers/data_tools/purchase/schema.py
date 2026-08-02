"""구매 Text2SQL에 허용된 table·column·업무 용어를 제공한다."""

from __future__ import annotations

from typing import TypedDict


class SchemaResource(TypedDict):
    """구매 Text2SQL이 추측 없이 참조할 수 있는 allowlist schema다."""

    tables: list[str]
    columns: dict[str, list[str]]
    business_glossary: dict[str, str]


def get_schema_resource() -> SchemaResource:
    """구매 소유 DDL에 대응하는 공개 가능한 schema와 용어집을 반환한다."""
    return {
        "tables": [
            "vendors", "purchase_requisitions", "purchase_requisition_lines",
            "purchase_orders", "purchase_order_lines", "goods_receipts",
            "goods_receipt_lines", "vendor_invoices", "vendor_invoice_lines",
            "procurement_reports", "vendor_contracts", "vendor_ratings",
            "invoice_matching",
        ],
        "columns": {
            "vendors": ["vendor_id", "vendor_code", "vendor_name", "vendor_type", "country", "payment_terms", "currency", "credit_limit", "is_active"],
            "purchase_orders": ["purchase_order_id", "vendor_id", "po_number", "po_date", "delivery_date", "subtotal", "tax_amount", "total_amount", "currency", "status"],
            "purchase_order_lines": ["purchase_order_line_id", "purchase_order_id", "item_id", "description", "quantity", "unit_price", "line_total", "quantity_received"],
            "goods_receipts": ["goods_receipt_id", "po_id", "vendor_id", "gr_number", "receipt_date", "warehouse_id"],
            "vendor_invoices": ["vendor_invoice_id", "vendor_id", "po_id", "invoice_number", "invoice_date", "due_date", "total_amount", "amount_paid", "outstanding_amount", "status"],
            "procurement_reports": ["procurement_report_id", "purchase_order_id", "vendor_id", "report_type", "period_start", "period_end", "total_spend", "po_count"],
            "vendor_contracts": ["vendor_contract_id", "vendor_id", "contract_number", "contract_type", "start_date", "end_date", "total_value", "status"],
            "vendor_ratings": ["vendor_rating_id", "vendor_id", "rating_period", "quality_score", "delivery_score", "pricing_score", "service_score", "overall_score"],
            "invoice_matching": ["invoice_match_id", "vendor_invoice_id", "po_id", "gr_id", "match_type", "invoice_amount", "po_amount", "gr_amount", "variance_amount", "match_status"],
        },
        "business_glossary": {
            "지출": "purchase_orders.total_amount",
            "공급업체": "vendors 테이블",
            "미지급금": "vendor_invoices.outstanding_amount",
            "발주": "purchase_orders",
            "입고": "goods_receipts",
            "3-way 매칭": "invoice_matching",
            "공급업체 평가": "vendor_ratings.overall_score",
        },
    }
