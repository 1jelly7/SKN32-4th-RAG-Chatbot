"""
schema.py의 정의로부터 MySQL DDL(CREATE TABLE)을 생성한다.

- 구매 도메인 내부 테이블 간 FK만 실제 FOREIGN KEY 제약으로 만든다.
- `purchase_order_lines.item_id`처럼 구매 도메인에 없는 테이블(items)을
  참조하는 컬럼은 일반 BIGINT 컬럼으로만 두고 제약을 걸지 않는다
  (ownership.md: 도메인은 서로의 적재 규칙을 직접 다루지 않는다).
- sales와 달리 업무키(po_number 등)에 UNIQUE 제약을 추가로 건다(schema.py의
  `unique` 필드) — 재실행 시 같은 업무키가 다른 PK로 중복 적재되는 것을 막는다.
"""

from __future__ import annotations

from etl.purchase.schema import PURCHASE_SCHEMA, TABLE_LOAD_ORDER


def _column_ddl(col: dict) -> str:
    parts = [f"`{col['name']}`", col["type"]]
    if not col["nullable"]:
        parts.append("NOT NULL")
    return " ".join(parts)


def build_create_table_sql(table_name: str) -> str:
    """구매 schema 정의 한 건을 idempotent CREATE TABLE SQL로 변환한다."""
    meta = PURCHASE_SCHEMA[table_name]
    columns = meta["columns"]
    pk = meta["pk"]

    lines = [f"CREATE TABLE IF NOT EXISTS `{table_name}` ("]
    col_lines = [f"    {_column_ddl(c)}" for c in columns]
    col_lines.append(f"    PRIMARY KEY (`{pk}`)")

    for c in columns:
        if c["unique"]:
            col_lines.append(
                f"    UNIQUE KEY `uk_{table_name}_{c['name']}` (`{c['name']}`)"
            )

    for c in columns:
        if c["fk_table"]:
            col_lines.append(
                f"    FOREIGN KEY (`{c['name']}`) "
                f"REFERENCES `{c['fk_table']}` (`{PURCHASE_SCHEMA[c['fk_table']]['pk']}`)"
            )

    lines.append(",\n".join(col_lines))
    lines.append(") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
    return "\n".join(lines)


def build_all_ddl() -> str:
    """FK 의존 순서로 모든 구매 테이블 DDL을 생성한다."""
    statements = [
        "-- 구매(Purchase) 도메인 테이블 DDL",
        "-- 생성 기준: ERP_Purchasing_Analytics.xlsx 실측 (5시트)",
        "-- 담당: 구매(rag_purchase) 도메인. 이 파일은 database/purchase/ 소유이며",
        "-- 통합/타 도메인 코드가 직접 수정하지 않는다.",
        "use purchase;",
        "",
    ]
    for table_name in TABLE_LOAD_ORDER:
        statements.append(build_create_table_sql(table_name))
        statements.append("")
    return "\n".join(statements)


if __name__ == "__main__":
    # database/purchase/ddl.sql 재생성용: python -m etl.purchase.ddl > database/purchase/ddl.sql
    print(build_all_ddl())
