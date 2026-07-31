"""판매 전용 쓰기 계정과 UPSERT 책임을 둔다."""

import pandas as pd

from etl.sales.types import LoadResult


class SalesETLMySQLClient:
    """판매 도메인에 허용된 테이블만 UPSERT하는 쓰기 어댑터."""

    def upsert(self, frame: pd.DataFrame, table: str) -> LoadResult:
        ...
