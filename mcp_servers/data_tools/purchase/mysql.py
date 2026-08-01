"""구매 Data MCP의 미구현 SELECT 전용 MySQL adapter."""

from __future__ import annotations

from typing import Any


class ReadOnlyMySQLClient:
    """SELECT 전용 chatbot_reader 계정을 사용하는 데이터 조회 어댑터."""
    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        """읽기 전용 연결 설정을 보관하고 자동 커밋을 사용하지 않는다."""
        # TODO(implementation): 읽기 설정만 보관하고 import/생성 시 접속하지 않는다.
        # 자격증명을 repr·로그·예외에 포함하지 않는다.
        ...

    def query(self, sql: str, timeout_seconds: int) -> list[dict[str, Any]]:
        """guard를 통과한 단일 SELECT를 timeout과 읽기 전용 세션으로 실행한다.

        실행 전 SQL을 재검증하거나 호출 계약으로 보장하고, cursor 결과를 컬럼명 기반 dict로
        변환한다. timeout·연결·DB 오류는 행 데이터나 자격증명 없이 구분 가능한 예외로 낸다.
        """
        # TODO(implementation): guard를 통과한 단일 SELECT만 read-only session에서
        # timeout·row limit과 함께 실행한다. 쓰기 SQL 거부, timeout, cursor/connection
        # cleanup, dict row 변환 테스트가 완료 조건이다.
        ...


def query_readonly(sql: str, timeout_seconds: int) -> list[dict[str, Any]]:
    """기본 ReadOnlyMySQLClient로 위임하는 편의 함수다."""
    # TODO(implementation): Settings의 구매 읽기 DB로 지연 생성한 client에 위임한다.
    ...
