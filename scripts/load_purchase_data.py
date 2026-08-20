# -*- coding: utf-8 -*-
"""
ERP_Purchasing_Data_Cleaned.xlsx의 각 시트를 purchase DB의 대응 테이블로 적재합니다.
외래키 제약을 지키기 위해 부모 테이블(vendors, purchase_requisitions, purchase_orders,
goods_receipts, vendor_invoices) -> 자식 테이블(각 *_lines) 순서로 적재합니다.

실행:
    python scripts/load_purchase_data.py /path/to/ERP_Purchasing_Data_Cleaned.xlsx
"""

from __future__ import annotations

import sys
from pathlib import Path

import openpyxl
import pymysql

DB_CONFIG = dict(
    host="127.0.0.1",
    user="JangGGo",
    password="1234",
    database="purchase",
    charset="utf8mb4",
)

# (시트명, 테이블명, 컬럼 매핑) - 컬럼 매핑은 "엑셀 헤더 -> DB 컬럼"입니다.
# 엑셀 헤더가 이미 스키마와 거의 1:1이라 소문자로만 바꾸면 됩니다.
SHEET_TABLE_ORDER = [
    "Vendors",
    "Purchase Requisitions",
    "Purchase Requisition Lines",
    "Purchase Orders",
    "Purchase Order Lines",
    "Goods Receipts",
    "Goods Receipt Lines",
    "Vendor Invoices",
    "Vendor Invoice Lines",
    "Procurement Reports",
]

SHEET_TO_TABLE = {
    "Vendors": "vendors",
    "Purchase Requisitions": "purchase_requisitions",
    "Purchase Requisition Lines": "purchase_requisition_lines",
    "Purchase Orders": "purchase_orders",
    "Purchase Order Lines": "purchase_order_lines",
    "Goods Receipts": "goods_receipts",
    "Goods Receipt Lines": "goods_receipt_lines",
    "Vendor Invoices": "vendor_invoices",
    "Vendor Invoice Lines": "vendor_invoice_lines",
    "Procurement Reports": "procurement_reports",
}


def header_to_column(header: str) -> str:
    """엑셀 헤더(예: Purchase_Order_ID)를 DB 컬럼명(purchase_order_id)으로 변환합니다."""
    return header.strip().lower()


def load_sheet(cursor, workbook, sheet_name: str) -> int:
    """한 구매 sheet를 대응 allowlisted table에 FK 순서를 지켜 적재한다."""
    table = SHEET_TO_TABLE[sheet_name]
    ws = workbook[sheet_name]

    rows = list(ws.iter_rows(values_only=True))
    header = [header_to_column(h) for h in rows[0]]
    data_rows = rows[1:]

    if not data_rows:
        return 0

    placeholders = ", ".join(["%s"] * len(header))
    columns = ", ".join(f"`{c}`" for c in header)
    sql = f"INSERT INTO `{table}` ({columns}) VALUES ({placeholders})"

    # None/빈 값은 그대로 NULL로 들어가게 둡니다.
    cursor.executemany(sql, data_rows)
    return len(data_rows)


def main() -> None:
    """구매 workbook 경로를 검증하고 부모→자식 순서로 배치 적재한다."""
    if len(sys.argv) < 2:
        print("사용법: python scripts/load_purchase_data.py <엑셀_파일_경로>")
        sys.exit(1)

    excel_path = Path(sys.argv[1])
    workbook = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)

    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            # 재실행 시 중복 적재를 막기 위해, 자식->부모 역순으로 기존 데이터를 비웁니다.
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            for sheet_name in reversed(SHEET_TABLE_ORDER):
                table = SHEET_TO_TABLE[sheet_name]
                cursor.execute(f"DELETE FROM `{table}`")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

            total = 0
            for sheet_name in SHEET_TABLE_ORDER:
                count = load_sheet(cursor, workbook, sheet_name)
                print(f"{sheet_name} -> {SHEET_TO_TABLE[sheet_name]}: {count}행 적재")
                total += count

        connection.commit()
        print(f"\n총 {total}행 적재 완료.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
