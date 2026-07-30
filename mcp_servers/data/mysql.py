from __future__ import annotations

from typing import Any


class ReadOnlyMySQLClient:
    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        ...

    def query(self, sql: str, timeout_seconds: int) -> list[dict[str, Any]]:
        ...


def query_readonly(sql: str, timeout_seconds: int) -> list[dict[str, Any]]:
    ...
