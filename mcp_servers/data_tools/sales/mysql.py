from __future__ import annotations

from typing import Any


class ReadOnlySalesMySQLClient:
    """판매 허용 View만 SELECT하는 읽기 전용 어댑터."""

    def query(self, sql: str, timeout_seconds: int) -> list[dict[str, Any]]:
        ...
