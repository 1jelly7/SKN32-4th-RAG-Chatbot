"""구매 Data MCP에서 SELECT만 실행하는 읽기 전용 MySQL adapter."""

from __future__ import annotations

import re
from typing import Any

import pymysql
import pymysql.cursors

from app.core.config import get_settings

# 사고를 막기 위한 이중 안전장치입니다. sql_guard 역할을 겸합니다.
_FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "GRANT", "REVOKE", "REPLACE", "MERGE",
)


class ReadOnlyMySQLClient:
    """구매 DB의 SELECT 전용 계정을 지연 연결 방식으로 사용한다."""
    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        """연결 설정만 보관하며 생성 시점에는 DB에 접속하지 않는다."""
        self._connection_kwargs = dict(
            host=host,
            user=user,
            password=password,
            database=database,
            cursorclass=pymysql.cursors.DictCursor,
            charset="utf8mb4",
            autocommit=False,
        )
        """연결 설정만 보관하며 생성 시점에는 DB에 접속하지 않는다."""
        self._connection_kwargs = dict(
            host=host,
            user=user,
            password=password,
            database=database,
            cursorclass=pymysql.cursors.DictCursor,
            charset="utf8mb4",
            autocommit=False,
        )

    def query(self, sql: str, timeout_seconds: int = 10) -> list[dict[str, Any]]:
        """단일 SELECT를 행 제한·timeout과 함께 실행하고 연결을 항상 닫는다."""
        stripped = sql.strip()
        normalized = stripped.rstrip(";")
        if ";" in normalized or "--" in normalized or "/*" in normalized or "#" in normalized:
            raise ValueError("단일 SELECT 문만 실행할 수 있습니다.")
        if not normalized.upper().startswith("SELECT"):
            raise ValueError("SELECT 문만 실행할 수 있습니다.")
        for keyword in _FORBIDDEN_KEYWORDS:
            if re.search(rf"\b{keyword}\b", normalized, re.IGNORECASE):
                raise ValueError(f"허용되지 않는 SQL 키워드가 포함되어 있습니다: {keyword}")
        if not re.search(r"\bLIMIT\b", normalized, re.IGNORECASE):
            normalized = f"{normalized} LIMIT 200"

        connection = pymysql.connect(**self._connection_kwargs)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION MAX_EXECUTION_TIME=%s", (timeout_seconds * 1000,))
                cursor.execute(normalized)
                return cursor.fetchall()
        finally:
            connection.close()


_default_client: ReadOnlyMySQLClient | None = None

def _get_default_client() -> ReadOnlyMySQLClient:
    """검증된 구매 DB 설정으로 기본 client를 한 번만 만든다."""
    global _default_client
    if _default_client is None:
        settings = get_settings()
        _default_client = ReadOnlyMySQLClient(
            host=settings.mysql_read_host,
            user=settings.mysql_read_user,
            password=settings.mysql_read_password,
            database=settings.purchase_db_database,
        )
    return _default_client


def query_readonly(sql: str, timeout_seconds: int = 10) -> list[dict[str, Any]]:
    """기본 구매 DB client에 검증된 SELECT 실행을 위임한다."""
    return _get_default_client().query(sql, timeout_seconds)
