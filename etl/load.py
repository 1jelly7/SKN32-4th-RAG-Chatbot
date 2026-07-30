import pandas as pd

from etl.types import LoadResult


class ETLMySQLClient:
    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        ...

    def upsert(self, frame: pd.DataFrame, table: str) -> LoadResult:
        ...


def upsert(frame: pd.DataFrame, table: str) -> LoadResult:
    ...
