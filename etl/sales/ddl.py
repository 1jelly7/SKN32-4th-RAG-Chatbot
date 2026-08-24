"""
schema.py의 정의로부터 MySQL DDL(CREATE TABLE)을 생성한다.

- sales 도메인 내부 테이블 간 FK만 실제 FOREIGN KEY 제약으로 만든다.
- Companies/Employees/Users 등 다른 도메인 테이블을 참조하는 컬럼은
  일반 BIGINT 컬럼으로만 두고 제약을 걸지 않는다(다른 도메인 테이블 존재를
  전제하지 않기 위함 - ownership.md: 도메인은 서로의 적재 규칙을 직접 다루지 않는다).
"""

from __future__ import annotations

from etl.sales.schema import SALES_SCHEMA, TABLE_LOAD_ORDER


def _column_ddl(col: dict) -> str:
    parts = [f"`{col['name']}`", col["type"]]
    if not col["nullable"]:
        parts.append("NOT NULL")
    return " ".join(parts)


def build_create_table_sql(table_name: str) -> str:
    """판매 schema 정의 한 건을 idempotent CREATE TABLE SQL로 변환한다."""
    meta = SALES_SCHEMA[table_name]
    columns = meta["columns"]
    pk = meta["pk"]

    lines = [f"CREATE TABLE IF NOT EXISTS `{table_name}` ("]
    col_lines = [f"    {_column_ddl(c)}" for c in columns]
    col_lines.append(f"    PRIMARY KEY (`{pk}`)")

    for c in columns:
        if c["fk_table"]:
            col_lines.append(
                f"    FOREIGN KEY (`{c['name']}`) "
                f"REFERENCES `{c['fk_table']}` (`{SALES_SCHEMA[c['fk_table']]['pk']}`)"
            )

    lines.append(",\n".join(col_lines))
    lines.append(") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
    return "\n".join(lines)


def build_all_ddl() -> str:
    """FK 의존 순서로 모든 판매 테이블 DDL을 생성한다."""
    statements = [
        "-- 판매(Sales) 도메인 테이블 DDL",
        "-- 생성 기준: ERP_Schema_v2_Corrected Column Dictionary",
        "-- 담당: 판매(rag_sales) 도메인. 이 파일은 database/sales/ 소유이며",
        "-- 통합/타 도메인 코드가 직접 수정하지 않는다.",
        "",
    ]
    for table_name in TABLE_LOAD_ORDER:
        statements.append(build_create_table_sql(table_name))
        statements.append("")
    return "\n".join(statements)


if __name__ == "__main__":
    # database/sales/ddl.sql 재생성용: python -m etl.sales.ddl > database/sales/ddl.sql
    print(build_all_ddl())
