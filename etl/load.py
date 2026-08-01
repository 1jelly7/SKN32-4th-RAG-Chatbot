import pandas as pd

from etl.types import LoadResult


class ETLMySQLClient:
    """ETL 전용 쓰기 계정으로만 적재하는 MySQL 어댑터.

    채팅용 read-only 계정이나 Data MCP의 연결을 재사용하지 않으며, 허용된 적재 테이블
    목록을 적용한다.
    """
    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        """쓰기 전용 연결 설정을 보관하고 비밀번호가 로그에 남지 않게 한다."""
        ...

    def upsert(self, frame: pd.DataFrame, table: str) -> LoadResult:
        """검증 완료된 frame만 단일 트랜잭션으로 INSERT/UPSERT한다.

        table은 allowlist로 검증하고 값은 항상 파라미터 바인딩한다. 실패 시 전체 rollback,
        성공 시 commit하며 inserted/updated 수를 정확히 분리해 반환한다.
        """
        ...


def upsert(frame: pd.DataFrame, table: str) -> LoadResult:
    """기본 ETLMySQLClient로 위임하는 적재 편의 함수다; 검증 단계를 우회하면 안 된다."""
    ...
