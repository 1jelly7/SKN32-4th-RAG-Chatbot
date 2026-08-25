"""
구매(Purchase) 도메인 테이블 스키마 정의.
`ERP_Purchasing_Analytics.xlsx`(5시트) 실측 기준으로 만들었다. 원천에 없는
컬럼(company_id, Vendor_Type, PII 등)은 만들어내지 않는다.
담당: 구매(rag_purchase) 도메인. 다른 도메인 테이블은 정의하지 않는다.

sales/schema.py와 달리 컬럼마다 `source`(원천 PascalCase 헤더)와 `unique`
(업무키 UNIQUE 제약 여부)를 추가로 갖는다 — DDL·rename·필수컬럼을 이 dict
하나에서 전부 파생시켜, ETL 코드 여러 곳에 흩어진 컬럼 정의가 서로 갈라지는
사고(이전 load.py/config.py/main.py가 각자 다른 스키마를 하드코딩했던 문제)를
구조적으로 막는다.
"""

from __future__ import annotations

# 적재 순서 (FK 의존성에 따른 topological order)
TABLE_LOAD_ORDER = [
    "vendors",
    "purchase_orders",
    "purchase_order_lines",
    "vendor_invoices",
    "goods_receipts",
]

# 엑셀 시트명 -> MySQL 테이블명 매핑
SHEET_TO_TABLE = {
    "Vendors": "vendors",
    "Purchase Orders": "purchase_orders",
    "PO Lines": "purchase_order_lines",
    "Invoices": "vendor_invoices",
    "Goods Receipts": "goods_receipts",
}

PURCHASE_SCHEMA = {
    "vendors": {
        "source_sheet": "Vendors",
        "columns": [
            {
                "name": "vendor_id",
                "source": "Vendor_ID",
                "type": "BIGINT",
                "is_pk": True,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
            {
                "name": "vendor_code",
                "source": "Vendor_Code",
                "type": "VARCHAR(20)",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": True,
            },
            {
                "name": "vendor_name",
                "source": "Vendor_Name",
                "type": "VARCHAR(200)",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
            {
                "name": "country",
                "source": "Country",
                "type": "VARCHAR(100)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
            {
                "name": "currency",
                "source": "Currency",
                "type": "VARCHAR(10)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
            {
                "name": "payment_terms",
                "source": "Payment_Terms",
                "type": "VARCHAR(20)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
            {
                "name": "is_active",
                "source": "Is_Active",
                "type": "TINYINT(1)",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
        ],
        "pk": "vendor_id",
    },
    "purchase_orders": {
        "source_sheet": "Purchase Orders",
        "columns": [
            {
                "name": "po_id",
                "source": "PO_ID",
                "type": "BIGINT",
                "is_pk": True,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
            {
                "name": "vendor_id",
                "source": "Vendor_ID",
                "type": "BIGINT",
                "is_pk": False,
                "fk_table": "vendors",
                "nullable": False,
                "unique": False,
            },
            {
                "name": "po_number",
                "source": "PO_Number",
                "type": "VARCHAR(30)",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": True,
            },
            {
                "name": "po_date",
                "source": "PO_Date",
                "type": "DATE",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
            {
                "name": "subtotal",
                "source": "Subtotal",
                "type": "DECIMAL(14,2)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
            {
                "name": "tax_amount",
                "source": "Tax_Amount",
                "type": "DECIMAL(14,2)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
            {
                "name": "total_amount",
                "source": "Total_Amount",
                "type": "DECIMAL(14,2)",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
            {
                "name": "currency",
                "source": "Currency",
                "type": "VARCHAR(10)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
            {
                "name": "status",
                "source": "Status",
                "type": "VARCHAR(30)",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
        ],
        "pk": "po_id",
    },
    "purchase_order_lines": {
        "source_sheet": "PO Lines",
        "columns": [
            {
                "name": "po_line_id",
                "source": "PO_Line_ID",
                "type": "BIGINT",
                "is_pk": True,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
            {
                "name": "po_id",
                "source": "PO_ID",
                "type": "BIGINT",
                "is_pk": False,
                "fk_table": "purchase_orders",
                "nullable": False,
                "unique": False,
            },
            # item_id는 구매 도메인에 items 테이블이 없어 FK 없이 일반 컬럼으로 둔다.
            {
                "name": "item_id",
                "source": "Item_ID",
                "type": "BIGINT",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
            {
                "name": "description",
                "source": "Description",
                "type": "VARCHAR(300)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
            {
                "name": "quantity",
                "source": "Quantity",
                "type": "INT",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
            # 실측: Unit_Price가 소수 4자리(예: 161.6126) -> (14,2)로 두면 quantity*unit_price != line_total이 된다.
            {
                "name": "unit_price",
                "source": "Unit_Price",
                "type": "DECIMAL(14,4)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
            {
                "name": "discount_percent",
                "source": "Discount_Percent",
                "type": "DECIMAL(5,2)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
            {
                "name": "line_total",
                "source": "Line_Total",
                "type": "DECIMAL(14,2)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
        ],
        "pk": "po_line_id",
    },
    "vendor_invoices": {
        "source_sheet": "Invoices",
        "columns": [
            {
                "name": "invoice_id",
                "source": "Invoice_ID",
                "type": "BIGINT",
                "is_pk": True,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
            {
                "name": "invoice_number",
                "source": "Invoice_Number",
                "type": "VARCHAR(30)",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": True,
            },
            {
                "name": "invoice_date",
                "source": "Invoice_Date",
                "type": "DATE",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
            {
                "name": "po_id",
                "source": "PO_ID",
                "type": "BIGINT",
                "is_pk": False,
                "fk_table": "purchase_orders",
                "nullable": False,
                "unique": False,
            },
            {
                "name": "vendor_id",
                "source": "Vendor_ID",
                "type": "BIGINT",
                "is_pk": False,
                "fk_table": "vendors",
                "nullable": False,
                "unique": False,
            },
            {
                "name": "subtotal",
                "source": "Subtotal",
                "type": "DECIMAL(14,2)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
            {
                "name": "tax_amount",
                "source": "Tax_Amount",
                "type": "DECIMAL(14,2)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
            {
                "name": "total_amount",
                "source": "Total_Amount",
                "type": "DECIMAL(14,2)",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
            {
                "name": "amount_paid",
                "source": "Amount_Paid",
                "type": "DECIMAL(14,2)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
            {
                "name": "outstanding_amount",
                "source": "Outstanding_Amount",
                "type": "DECIMAL(14,2)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
            {
                "name": "currency",
                "source": "Currency",
                "type": "VARCHAR(10)",
                "is_pk": False,
                "fk_table": None,
                "nullable": True,
                "unique": False,
            },
            {
                "name": "status",
                "source": "Status",
                "type": "VARCHAR(30)",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
        ],
        "pk": "invoice_id",
    },
    "goods_receipts": {
        "source_sheet": "Goods Receipts",
        "columns": [
            {
                "name": "gr_id",
                "source": "GR_ID",
                "type": "BIGINT",
                "is_pk": True,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
            {
                "name": "gr_number",
                "source": "GR_Number",
                "type": "VARCHAR(30)",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": True,
            },
            {
                "name": "receipt_date",
                "source": "Receipt_Date",
                "type": "DATE",
                "is_pk": False,
                "fk_table": None,
                "nullable": False,
                "unique": False,
            },
            {
                "name": "po_id",
                "source": "PO_ID",
                "type": "BIGINT",
                "is_pk": False,
                "fk_table": "purchase_orders",
                "nullable": False,
                "unique": False,
            },
            {
                "name": "vendor_id",
                "source": "Vendor_ID",
                "type": "BIGINT",
                "is_pk": False,
                "fk_table": "vendors",
                "nullable": False,
                "unique": False,
            },
        ],
        "pk": "gr_id",
    },
}


def column_mapping_for(table: str) -> dict[str, str]:
    """원천 헤더(PascalCase) -> DB 컬럼명(snake_case) 매핑. transform()의 rename에 쓴다."""
    return {c["source"]: c["name"] for c in PURCHASE_SCHEMA[table]["columns"]}


def required_columns_for(table: str) -> list[str]:
    """PK + NOT NULL 컬럼을 필수 컬럼으로 취급한다(rename 이후 이름 기준)."""
    return [
        c["name"]
        for c in PURCHASE_SCHEMA[table]["columns"]
        if c["is_pk"] or not c["nullable"]
    ]


def type_mapping_for(table: str) -> dict[str, str]:
    """DB 타입을 pandas astype 문자열로 변환해 transform()의 타입 강제에 쓴다."""
    mapping: dict[str, str] = {}
    for c in PURCHASE_SCHEMA[table]["columns"]:
        db_type = c["type"]
        if db_type.startswith("BIGINT") or db_type.startswith("INT"):
            mapping[c["name"]] = "Int64"
        elif db_type.startswith("DECIMAL"):
            mapping[c["name"]] = "float64"
        elif db_type.startswith("TINYINT"):
            mapping[c["name"]] = "Int64"
        # DATE/VARCHAR는 강제 변환하지 않는다(문자열 그대로 MySQL DATE 컬럼에 바인딩 가능).
    return mapping


def boolean_columns(table: str) -> list[str]:
    """TINYINT(1)로 저장되는 bool 컬럼 목록."""
    return [
        c["name"]
        for c in PURCHASE_SCHEMA[table]["columns"]
        if c["type"].startswith("TINYINT")
    ]
