from __future__ import annotations

from typing import TypedDict


class SQLPolicy(TypedDict):
    allowed_tables: list[str]
    allowed_columns: dict[str, list[str]]
    default_limit: int
    forbidden_keywords: list[str]


def load_sql_policy(policy_path: str) -> SQLPolicy:
    ...


def validate_sql(sql: str, policy: SQLPolicy) -> str:
    ...
