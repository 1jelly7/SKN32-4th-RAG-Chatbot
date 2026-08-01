"""구매 도메인 쓰기 계정으로 검증된 frame만 적재할 미구현 adapter."""

import pandas as pd

from etl.purchase.types import LoadResult


class ETLMySQLClient:
    """ETL 전용 쓰기 계정으로만 적재하는 MySQL 어댑터.

    채팅용 read-only 계정이나 Data MCP의 연결을 재사용하지 않으며, 허용된 적재 테이블
    목록을 적용한다.
    """
    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        """쓰기 전용 연결 설정을 보관하고 비밀번호가 로그에 남지 않게 한다."""
        # TODO(implementation): 구매 쓰기 연결 설정만 보관하고 import/생성 시 접속하지
        # 않는다. read-only chatbot 계정과 자격증명 로그 사용을 금지한다.
        ...

    def upsert(self, frame: pd.DataFrame, table: str) -> LoadResult:
        """검증 완료된 frame만 단일 트랜잭션으로 INSERT/UPSERT한다.

        table은 allowlist로 검증하고 값은 항상 파라미터 바인딩한다. 실패 시 전체 rollback,
        성공 시 commit하며 inserted/updated 수를 정확히 분리해 반환한다.
        """
        # TODO(implementation): 구매 allowlist와 자연키를 기준으로 parameterized UPSERT를
        # 단일 transaction에서 실행한다. 재실행 멱등성, rollback, inserted/updated 수,
        # 미허용 table 거부 테스트가 완료 조건이다.
        ...


def upsert(frame: pd.DataFrame, table: str) -> LoadResult:
    """기본 ETLMySQLClient로 위임하는 적재 편의 함수다; 검증 단계를 우회하면 안 된다."""
    # TODO(implementation): 검증 완료 precondition을 보존해 구매 client에만 위임한다.
    ...
