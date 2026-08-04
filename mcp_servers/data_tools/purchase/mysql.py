"""구매 Data MCP에서 SELECT만 실행하는 읽기 전용 MySQL adapter."""

from __future__ import annotations

import re
from typing import Any

import pymysql
import pymysql.cursors

from app.core.config import get_settings
from app.core.db_pool import get_pool

# 사고를 막기 위한 이중 안전장치입니다. sql_guard 역할을 겸합니다.
_FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "GRANT", "REVOKE", "REPLACE", "MERGE",
)


class ReadOnlyMySQLClient:
    """구매 DB의 SELECT 전용 계정을 공유 풀에서 연결을 빌려 사용한다."""
    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        """연결 풀을 준비하되 생성 시점에는 DB에 접속하지 않는다(풀도 지연 연결)."""
        self._pool = get_pool(host, user, password, database, autocommit=False)

    def query(self, sql: str, timeout_seconds: int = 10) -> list[dict[str, Any]]:
        """단일 SELECT를 행 제한·timeout과 함께 실행하고 연결을 풀에 반납한다."""
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

        connection = self._pool.connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION MAX_EXECUTION_TIME=%s", (timeout_seconds * 1000,))
                cursor.execute(normalized)
                return cursor.fetchall()
        finally:
            # 풀에서 빌린 연결이라 close()해도 TCP는 끊기지 않고 풀에 반납된다.
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