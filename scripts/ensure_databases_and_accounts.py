# -*- coding: utf-8 -*-
"""완전히 빈 MySQL 상태에서, 이 프로젝트가 필요로 하는 DB 4개와 쓰기(admin) 계정을
전부 만듭니다. 이미 되어 있는 건 건너뛰고 다음으로 넘어갑니다.

이 스크립트만 root 권한 계정(.env의 MYSQL_ROOT_*)을 씁니다 - 애플리케이션 자체는
이 계정을 전혀 모르고, 도메인별 전용 계정만 씁니다.

멱등성(idempotent) 원칙:
    - CREATE DATABASE IF NOT EXISTS  -> 이미 있으면 그냥 넘어감
    - CREATE USER IF NOT EXISTS      -> 이미 있으면 새로 안 만듦
    - ALTER USER ... IDENTIFIED BY   -> 매번 실행 - 계정이 예전에 다른 비밀번호로
      만들어져 있었어도, .env의 현재 값으로 강제로 맞춘다(이번 세션에서 반복됐던
      "Access denied" 사고의 근본 원인이 이거였음 - CREATE USER IF NOT EXISTS는
      비밀번호를 갱신 안 해준다).

실행:
    python scripts/ensure_databases_and_accounts.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _root_connection():
    import pymysql
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
    host = os.getenv("MYSQL_ROOT_HOST", "127.0.0.1")
    user = os.getenv("MYSQL_ROOT_USER", "root")
    password = os.getenv("MYSQL_ROOT_PASSWORD", "")
    return pymysql.connect(host=host, user=user, password=password, charset="utf8mb4", autocommit=True)


def _ensure_database(cursor, name: str) -> None:
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    print(f"  DB `{name}` 준비됨")


def _escape_percent_for_params(value: str) -> str:
    """pymysql이 매개변수(%s)를 치환할 때 파이썬 %-포매팅을 그대로 쓰기 때문에,
    쿼리 문자열 안에 있는 리터럴 '%'(MySQL 호스트 와일드카드 등)이 %s와 충돌한다.
    매개변수를 같이 넘기는 execute() 호출에서만 이 함수로 미리 이스케이프해야 한다
    (매개변수 없이 execute(query)만 부르는 경우는 치환 자체가 없어서 이스케이프하면
    안 된다 - 그러면 반대로 '%%'가 그대로 SQL에 들어가 버린다).
    """
    return value.replace("%", "%%")


def _ensure_write_account(cursor, user: str, password: str, database: str) -> None:
    """쓰기 계정을 만들고, DDL(CREATE TABLE 포함)까지 필요한 ALL PRIVILEGES를 준다.

    ETL(etl/purchase, etl/sales)과 document_db.ensure_schema()가 테이블을 직접
    CREATE TABLE로 만들기 때문에, SELECT/INSERT/UPDATE/DELETE만으로는 부족하다.
    """
    if not user or not password:
        print(f"  경고: {database}용 계정 정보가 .env에 비어 있어 건너뜁니다 (user={user!r})")
        return
    for host in ("%", "localhost"):
        escaped_host = _escape_percent_for_params(host)
        cursor.execute(f"CREATE USER IF NOT EXISTS '{user}'@'{escaped_host}' IDENTIFIED BY %s", (password,))
        cursor.execute(f"ALTER USER '{user}'@'{escaped_host}' IDENTIFIED BY %s", (password,))
    # 아래 두 GRANT는 매개변수를 안 넘기므로(파이썬 %-포매팅이 아예 안 일어남) 호스트를
    # 이스케이프하면 안 된다 - 원래 문자 그대로(단일 '%') 넘겨야 MySQL이 와일드카드로 인식한다.
    cursor.execute(f"GRANT ALL PRIVILEGES ON `{database}`.* TO '{user}'@'%'")
    cursor.execute(f"GRANT ALL PRIVILEGES ON `{database}`.* TO '{user}'@'localhost'")
    print(f"  계정 `{user}`가 `{database}`에 쓰기 권한으로 준비됨(비밀번호 동기화 포함)")


def main() -> None:
    from app.core.config import get_settings

    settings = get_settings()

    print("root 계정으로 접속 중...")
    connection = _root_connection()
    try:
        with connection.cursor() as cursor:
            print("\n[1/2] 데이터베이스 4개 확인/생성")
            _ensure_database(cursor, "account_db")
            _ensure_database(cursor, settings.purchase_db_database)
            _ensure_database(cursor, settings.sales_db_database)
            _ensure_database(cursor, settings.document_db_database)

            print("\n[2/2] 쓰기(admin) 계정 확인/생성 + 비밀번호 동기화")

            # account_db: Django가 쓰는 계정 (.env의 ACCOUNT_DB_USER/PASSWORD)
            account_db_user = os.getenv("ACCOUNT_DB_USER", "")
            account_db_password = os.getenv("ACCOUNT_DB_PASSWORD", "")
            if not account_db_user:
                print(
                    "  경고: ACCOUNT_DB_USER가 .env에 비어 있습니다. "
                    "Django가 account_db에 접속 못 하니, .env에 값을 채운 뒤 이 스크립트를 다시 실행하세요."
                )
            else:
                _ensure_write_account(cursor, account_db_user, account_db_password, "account_db")

            # purchase: 도메인 전용 계정
            _ensure_write_account(
                cursor, settings.purchase_db_user, settings.purchase_db_password, settings.purchase_db_database
            )

            # sales + document(erp_system): 공용 계정(mysql_write_*, 흔히 JangGGo)
            _ensure_write_account(
                cursor, settings.mysql_write_user, settings.mysql_write_password, settings.sales_db_database
            )
            _ensure_write_account(
                cursor, settings.mysql_write_user, settings.mysql_write_password, settings.document_db_database
            )
    finally:
        connection.close()

    print("\n완료. 이제 setup_all.py의 나머지 단계(migration/ETL/인덱싱)를 진행할 수 있습니다.")


if __name__ == "__main__":
    main()