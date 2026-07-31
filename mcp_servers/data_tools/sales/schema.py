from __future__ import annotations

from typing import TypedDict


class SchemaResource(TypedDict):
    allowed_tables: list[str]
    allowed_columns: dict[str, list[str]]
    business_glossary: dict[str, str]


def get_schema_resource() -> SchemaResource:
    """판매 도메인에서 승인된 View·컬럼·용어만 반환한다."""
    ...
