"""판매 Data MCP에서 guard된 SELECT만 실행하는 읽기 전용 MySQL adapter."""

from __future__ import annotations

import re
from typing import Any

import pymysql
import pymysql.cursors

from app.core.config import get_settings

_FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "GRANT", "REVOKE", "REPLACE", "MERGE",
)


class ReadOnlyMySQLClient:
    """SELECT 전용 chatbot_reader 계정을 사용하는 데이터 조회 어댑터."""

    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        """읽기 전용 연결 설정을 보관하고 자동 커밋을 사용하지 않는다."""
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
        """guard를 통과한 단일 SELECT를 timeout과 읽기 전용 세션으로 실행한다."""
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
                rows = cursor.fetchall()
            return rows
        finally:
            connection.close()


_default_client: ReadOnlyMySQLClient | None = None


def _get_default_client() -> ReadOnlyMySQLClient:
    global _default_client
    if _default_client is None:
        settings = get_settings()
        _default_client = ReadOnlyMySQLClient(
            host=settings.mysql_read_host,
            user=settings.mysql_read_user,
            password=settings.mysql_read_password,
            database=settings.sales_db_database,
        )
    return _default_client


def query_readonly(sql: str, timeout_seconds: int = 10) -> list[dict[str, Any]]:
    """기본 ReadOnlyMySQLClient로 위임하는 편의 함수다."""
    return _get_default_client().query(sql, timeout_seconds)
