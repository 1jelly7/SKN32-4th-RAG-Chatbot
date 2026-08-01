"""소유자 결정 전 보존하는 legacy finance 쓰기 adapter 스켈레톤."""

import pandas as pd

from etl.finance.types import LoadResult


class ETLMySQLClient:
    """ETL 전용 쓰기 계정으로만 적재하는 MySQL 어댑터.

    채팅용 read-only 계정이나 Data MCP의 연결을 재사용하지 않으며, 허용된 적재 테이블
    목록을 적용한다.
    """
    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        """쓰기 전용 연결 설정을 보관하고 비밀번호가 로그에 남지 않게 한다."""
        # TODO(contract clarification): legacy 유지와 table allowlist 확정 전 연결을
        # 구현하지 않는다. purchase ETL 쓰기 경계를 우회하면 안 된다.
        ...

    def upsert(self, frame: pd.DataFrame, table: str) -> LoadResult:
        """검증 완료된 frame만 단일 트랜잭션으로 INSERT/UPSERT한다.

        table은 allowlist로 검증하고 값은 항상 파라미터 바인딩한다. 실패 시 전체 rollback,
        성공 시 commit하며 inserted/updated 수를 정확히 분리해 반환한다.
        """
        # TODO(implementation): 채택될 경우 검증된 frame만 transaction/parameter binding로
        # 적재하고 멱등성·rollback·allowlist를 테스트한다.
        ...


def upsert(frame: pd.DataFrame, table: str) -> LoadResult:
    """기본 ETLMySQLClient로 위임하는 적재 편의 함수다; 검증 단계를 우회하면 안 된다."""
    # TODO(contract clarification): legacy adapter 채택 전 기본 client를 만들지 않는다.
    ...
