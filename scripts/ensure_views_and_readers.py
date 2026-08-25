# -*- coding: utf-8 -*-
"""purchase/sales 뷰와 읽기 전용(reader) 계정을 만들고 권한을 부여합니다.

ETL(테이블 생성+데이터 적재)이 끝난 뒤에 실행해야 합니다 - 뷰가 참조할 테이블이
그 전에는 존재하지 않기 때문입니다.

멱등성: CREATE OR REPLACE VIEW는 원래 몇 번을 다시 실행해도 안전합니다.
reader 계정도 ensure_databases_and_accounts.py와 동일하게 CREATE USER IF NOT
EXISTS + ALTER USER로 비밀번호를 매번 강제 동기화합니다.

실행:
    python scripts/ensure_views_and_readers.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# (뷰 SQL 파일, 그 안에 정의된 뷰 이름 목록, reader 계정이 접속할 DB)
_DOMAINS = [
    {
        "views_sql": PROJECT_ROOT / "database" / "purchase" / "views.sql",
        "database_setting": "purchase_db_database",
        "view_names": [
            "v_purchase_order",
            "v_purchase_order_line",
            "v_vendor",
            "v_vendor_invoice",
            "v_purchase_order_status",
        ],
        "reader_user_env": "PURCHASE_READ_USER",
        "reader_password_env": "PURCHASE_READ_PASSWORD",
    },
    {
        "views_sql": PROJECT_ROOT / "database" / "sales" / "views.sql",
        "database_setting": "sales_db_database",
        "view_names": None,  # sales views.sql 안의 뷰를 실제로 파싱해서 채운다(아래 참고)
        "reader_user_env": "SALES_READ_USER",
        "reader_password_env": "SALES_READ_PASSWORD",
    },
]


def _root_connection():
    import pymysql
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
    host = os.getenv("MYSQL_ROOT_HOST", "127.0.0.1")
    user = os.getenv("MYSQL_ROOT_USER", "root")
    password = os.getenv("MYSQL_ROOT_PASSWORD", "")
    return pymysql.connect(host=host, user=user, password=password, charset="utf8mb4", autocommit=True)


def _extract_view_names(sql_text: str) -> list[str]:
    """'CREATE OR REPLACE VIEW 이름 AS' 패턴에서 뷰 이름만 뽑는다."""
    import re

    return re.findall(r"CREATE\s+OR\s+REPLACE\s+VIEW\s+`?(\w+)`?\s+AS", sql_text, flags=re.IGNORECASE)


def _run_sql_script(cursor, sql_path: Path, database: str) -> None:
    if not sql_path.exists():
        print(f"  경고: {sql_path} 파일이 없습니다 - 건너뜁니다.")
        return
    sql_text = sql_path.read_text(encoding="utf-8")
    code_lines = [line for line in sql_text.splitlines() if not line.strip().startswith("--")]
    cleaned_sql = "\n".join(code_lines)
    statements = [s.strip() for s in cleaned_sql.split(";") if s.strip()]

    cursor.execute(f"USE `{database}`")
    for statement in statements:
        if statement.upper().startswith("USE "):
            continue  # 이미 위에서 DB를 선택했으므로 중복 USE는 건너뛴다
        cursor.execute(statement)
    print(f"  {sql_path.name} 적용 완료 ({len(statements)}개 문장)")


def _escape_percent_for_params(value: str) -> str:
    """pymysql이 매개변수(%s)를 치환할 때 파이썬 %-포매팅을 그대로 쓰기 때문에,
    쿼리 문자열 안에 있는 리터럴 '%'(MySQL 호스트 와일드카드 등)이 %s와 충돌한다.
    매개변수를 같이 넘기는 execute() 호출에서만 이 함수로 미리 이스케이프해야 한다.
    """
    return value.replace("%", "%%")


def _ensure_reader_account(cursor, user: str, password: str, database: str, view_names: list[str]) -> None:
    if not user or not password:
        print(f"  경고: {database}용 reader 계정 정보가 .env에 비어 있어 건너뜁니다 (user={user!r})")
        return
    for host in ("%", "localhost"):
        escaped_host = _escape_percent_for_params(host)
        cursor.execute(f"CREATE USER IF NOT EXISTS '{user}'@'{escaped_host}' IDENTIFIED BY %s", (password,))
        cursor.execute(f"ALTER USER '{user}'@'{escaped_host}' IDENTIFIED BY %s", (password,))
        for view_name in view_names:
            # 원본 테이블 권한은 절대 주지 않는다 - 뷰에만 SELECT를 허용한다.
            # 이 GRANT는 매개변수를 안 넘기므로 host를 이스케이프하지 않은 원래 값을 쓴다.
            cursor.execute(f"GRANT SELECT ON `{database}`.`{view_name}` TO '{user}'@'{host}'")
    print(f"  reader `{user}`가 뷰 {len(view_names)}개에 SELECT 권한으로 준비됨(비밀번호 동기화 포함)")


def main() -> None:
    from app.core.config import get_settings

    settings = get_settings()

    print("root 계정으로 접속 중...")
    connection = _root_connection()
    try:
        with connection.cursor() as cursor:
            print("\n[1/2] 뷰 생성/갱신")
            for domain in _DOMAINS:
                database = getattr(settings, domain["database_setting"])
                sql_text = domain["views_sql"].read_text(encoding="utf-8") if domain["views_sql"].exists() else ""
                view_names = domain["view_names"] or _extract_view_names(sql_text)
                _run_sql_script(cursor, domain["views_sql"], database)
                domain["_resolved_view_names"] = view_names
                domain["_resolved_database"] = database

            print("\n[2/2] reader 계정 확인/생성 + 권한 부여 + 비밀번호 동기화")
            for domain in _DOMAINS:
                reader_user = os.getenv(domain["reader_user_env"], "")
                reader_password = os.getenv(domain["reader_password_env"], "")
                _ensure_reader_account(
                    cursor,
                    reader_user,
                    reader_password,
                    domain["_resolved_database"],
                    domain["_resolved_view_names"],
                )
    finally:
        connection.close()

    print("\n완료. 뷰와 reader 계정이 전부 준비됐습니다.")


if __name__ == "__main__":
    main()