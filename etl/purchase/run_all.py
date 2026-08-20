"""구매 5개 테이블 전체를 순서대로 적재하는 배치 진입점.

`scripts/load_mysql_data.py`(통합 담당)가 도메인 선택 후 이 모듈을 호출하는 것을
최종 형태로 상정한다(etl/sales/run_all.py와 동형). 현재는 단독 실행 가능하게 제공한다.

    python -m etl.purchase.run_all [xlsx_path]
"""
from __future__ import annotations

import sys
from pathlib import Path

from etl.purchase.pipeline import run_excel_pipeline
from etl.purchase.schema import PURCHASE_SCHEMA, SHEET_TO_TABLE, TABLE_LOAD_ORDER

DEFAULT_SOURCE = Path("data/raw/source_data/ERP_Purchasing_Analytics.xlsx")


def required_columns_for(table: str) -> list[str]:
    """PK + NOT NULL 컬럼을 필수 컬럼으로 취급한다."""
    return [
        c["name"]
        for c in PURCHASE_SCHEMA[table]["columns"]
        if c["is_pk"] or not c["nullable"]
    ]


def run_all(xlsx_path: Path = DEFAULT_SOURCE) -> None:
    """구매 workbook의 모든 시트를 FK 의존 순서로 적재한다."""
    table_to_sheet = {table: sheet for sheet, table in SHEET_TO_TABLE.items()}
    for table in TABLE_LOAD_ORDER:
        sheet = table_to_sheet[table]
        run_excel_pipeline(xlsx_path, sheet, table, required_columns_for(table))


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    run_all(source)
