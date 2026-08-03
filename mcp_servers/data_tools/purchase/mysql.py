"""구매 Data MCP에서 guard된 SELECT만 실행하는 읽기 전용 MySQL adapter.

환경변수:
- PURCHASE_READ_HOST / PURCHASE_READ_USER / PURCHASE_READ_PASSWORD / PURCHASE_READ_DATABASE
  (읽기 전용 purchase_reader 계정 — 실제 행 데이터 조회)
- MYSQL_WRITE_HOST / MYSQL_WRITE_USER / MYSQL_WRITE_PASSWORD + PURCHASE_DB_DATABASE
  (EXPLAIN 사전검증 전용. 아래 ExplainOnlyMySQLClient 설명 참고)
"""

from __future__ import annotations

from typing import Any

import pymysql
import pymysql.cursors

from app.core.config import get_settings
from mcp_servers.data_tools.purchase.sql_guard import validate_and_normalize


class ReadOnlyMySQLClient:
    """SELECT 전용 purchase_reader 계정을 사용하는 데이터 조회 어댑터."""

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
            connect_timeout=5,
            read_timeout=10,
        )

    def query(self, sql: str, timeout_seconds: int = 10) -> list[dict[str, Any]]:
        """guard를 통과한 단일 SELECT를 timeout과 읽기 전용 세션으로 실행한다."""
        normalized = validate_and_normalize(sql)

        connection = pymysql.connect(**self._connection_kwargs)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION MAX_EXECUTION_TIME=%s", (timeout_seconds * 1000,))
                cursor.execute(normalized)
                rows = cursor.fetchall()
            return rows
        finally:
            connection.close()


class ExplainOnlyMySQLClient:
    """EXPLAIN 검증 전용 adapter. 행 데이터는 절대 반환하지 않는다.

    MySQL은 SQL SECURITY DEFINER 뷰에 대해 실제 SELECT는 뷰 생성자 권한으로
    돌려주지만, EXPLAIN은 호출 계정이 원본 테이블 권한을 직접 가져야 한다
    (그렇지 않으면 "lacking privileges for underlying table" 오류가 난다).
    그래서 EXPLAIN만 admin 계정(mysql_write_*)으로 실행한다 — EXPLAIN은 실행
    계획 정보만 돌려주고 실제 행 데이터는 절대 반환하지 않으므로, 실제 데이터
    조회를 purchase_reader로만 제한하는 원칙은 그대로 유지된다.
    """

    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        self._connection_kwargs = dict(
            host=host,
            user=user,
            password=password,
            database=database,
            cursorclass=pymysql.cursors.DictCursor,
            charset="utf8mb4",
            autocommit=False,
            connect_timeout=5,
            read_timeout=10,
        )

    def explain(self, sql: str, timeout_seconds: int = 10) -> None:
        """guard를 통과한 SQL을 실제로 실행하지 않고 EXPLAIN으로만 채점한다.

        문법 오류·존재하지 않는 컬럼 같은 문제를 실제 데이터에 닿기 전에 잡는다.
        통과하면 아무 것도 반환하지 않고, 실패하면 pymysql 예외를 그대로 낸다
        (호출부가 그 메시지를 LLM에게 보여주고 재작성을 요청한다).
        """
        normalized = validate_and_normalize(sql)
        connection = pymysql.connect(**self._connection_kwargs)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION MAX_EXECUTION_TIME=%s", (timeout_seconds * 1000,))
                cursor.execute(f"EXPLAIN {normalized}")
                cursor.fetchall()
        finally:
            connection.close()


_default_client: ReadOnlyMySQLClient | None = None
_default_explain_client: ExplainOnlyMySQLClient | None = None


def _get_default_client() -> ReadOnlyMySQLClient:
    """검증된 구매 읽기전용(purchase_reader) 설정으로 기본 client를 한 번만 만든다.

    환경변수에서 읽기:
    - PURCHASE_READ_HOST
    - PURCHASE_READ_USER
    - PURCHASE_READ_PASSWORD
    - PURCHASE_READ_DATABASE
    """
    global _default_client
    if _default_client is None:
        settings = get_settings()
        _default_client = ReadOnlyMySQLClient(
            host=settings.purchase_read_host,
            user=settings.purchase_read_user,
            password=settings.purchase_read_password,
            database=settings.purchase_read_database,
        )
    return _default_client


def _get_default_explain_client() -> ExplainOnlyMySQLClient:
    """admin(mysql_write_*) 계정으로 EXPLAIN 전용 client를 한 번만 만든다."""
    global _default_explain_client
    if _default_explain_client is None:
        settings = get_settings()
        _default_explain_client = ExplainOnlyMySQLClient(
            host=settings.mysql_write_host,
            user=settings.mysql_write_user,
            password=settings.mysql_write_password,
            database=settings.purchase_db_database,
        )
    return _default_explain_client


def query_readonly(sql: str, timeout_seconds: int = 10) -> list[dict[str, Any]]:
    """기본 ReadOnlyMySQLClient로 위임하는 편의 함수다."""
    return _get_default_client().query(sql, timeout_seconds)


def explain_readonly(sql: str, timeout_seconds: int = 10) -> None:
    """기본 ExplainOnlyMySQLClient로 위임하는 편의 함수다."""
    _get_default_explain_client().explain(sql, timeout_seconds)