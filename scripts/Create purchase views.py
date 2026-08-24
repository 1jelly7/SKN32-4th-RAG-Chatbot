# -*- coding: utf-8 -*-
"""
purchase_db에 5개의 RAG용 뷰를 생성합니다.
.env 설정을 자동으로 사용하지만, 구매 DB는 명시적으로 'purchase_db'를 사용합니다.
프로젝트 루트를 자동으로 감지합니다.

실행:
    python scripts/create_purchase_views.py
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# 프로젝트 루트 자동 감지 (scripts/ 폴더에서 실행되어도 동작)
current_file = Path(__file__).resolve()
scripts_dir = current_file.parent
project_root = scripts_dir.parent

# sys.path에 프로젝트 루트 추가
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 작업 디렉토리를 프로젝트 루트로 변경 (.env 파일 찾기용)
os.chdir(project_root)

import pymysql

# .env에서 설정 읽기 (get_settings() 함수 사용)
from app.core.config import get_settings

# 설정 로드
settings = get_settings()

# 쓰기 계정을 사용하되, 구매 DB 명시 (purchase_db)
DB_CONFIG = dict(
    host=settings.mysql_write_host,
    user=settings.mysql_write_user,
    password=settings.mysql_write_password,
    database="purchase_db",  # ← 명시적으로 purchase_db 지정
    charset="utf8mb4",
)

# 생성할 5개 뷰의 DDL
VIEWS = {
    "v_purchase_order": """
        CREATE OR REPLACE VIEW v_purchase_order AS
        SELECT 
          PO_ID,
          company_id,
          PO_Number,
          PO_Date,
          Vendor_ID,
          Subtotal,
          Tax_Amount,
          Total_Amount,
          Currency,
          Status
        FROM purchase_orders
        WHERE Status != 'Cancelled'
    """,
    "v_purchase_order_line": """
        CREATE OR REPLACE VIEW v_purchase_order_line AS
        SELECT 
          pol.PO_Line_ID,
          pol.company_id,
          pol.PO_ID,
          po.Vendor_ID,
          po.PO_Date,
          po.Status,
          pol.Item_ID,
          pol.Item_Code,
          pol.Description,
          pol.Quantity,
          pol.Unit_Price,
          pol.Discount_Percent,
          pol.Line_Total
        FROM po_lines pol
        INNER JOIN purchase_orders po ON pol.PO_ID = po.PO_ID
        WHERE po.Status != 'Cancelled'
    """,
    "v_vendor": """
        CREATE OR REPLACE VIEW v_vendor AS
        SELECT 
          Vendor_ID,
          company_id,
          Vendor_Code,
          Vendor_Name,
          Vendor_Type,
          Country,
          Currency,
          Payment_Terms,
          Active
        FROM vendors
    """,
    "v_vendor_invoice": """
        CREATE OR REPLACE VIEW v_vendor_invoice AS
        SELECT 
          Invoice_ID,
          company_id,
          Invoice_Number,
          Invoice_Date,
          PO_ID,
          Vendor_ID,
          Due_Date,
          Subtotal,
          Tax_Amount,
          Total_Amount,
          Amount_Paid,
          Outstanding_Amount,
          Currency,
          Payment_Status
        FROM invoices
    """,
    "v_goods_receipt": """
        CREATE OR REPLACE VIEW v_goods_receipt AS
        SELECT 
          GR_ID,
          company_id,
          GR_Number,
          PO_ID,
          Vendor_ID,
          Receipt_Date,
          Status
        FROM goods_receipts
    """,
}


def main() -> None:
    """purchase_db에 5개 뷰를 생성한다."""

    print("=" * 70)
    print("📺 Purchase 뷰 생성 스크립트")
    print("=" * 70)
    print(f"\n📝 프로젝트 루트: {project_root}")
    print(f"📝 DB 설정: .env 에서 자동 로드")
    print(f"  ├─ 호스트: {DB_CONFIG['host']}")
    print(f"  ├─ 사용자: {DB_CONFIG['user']}")
    print(f"  ├─ DB명: {DB_CONFIG['database']} (구매 전용)")
    print(f"  └─ 생성할 뷰: {len(VIEWS)}개\n")

    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            for idx, (view_name, sql) in enumerate(VIEWS.items(), 1):
                try:
                    cursor.execute(sql)
                    print(f"  ✅ [{idx}/{len(VIEWS)}] {view_name:30} 생성 완료")
                except Exception as e:
                    print(f"  ❌ [{idx}/{len(VIEWS)}] {view_name} 생성 실패: {str(e)}")
                    raise

        connection.commit()

        print(f"\n" + "=" * 70)
        print(f"✅ 모든 뷰 생성 완료!")
        print(f"=" * 70)
        print(f"\n생성된 뷰 (purchase_db):")
        for view_name in VIEWS.keys():
            print(f"  • {view_name}")

        print(f"\n다음 단계: LLM 프롬프트 설정 (schema.py 작성)")

    except Exception as e:
        print(f"\n❌ 뷰 생성 실패: {str(e)}")
        connection.rollback()
        sys.exit(1)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
