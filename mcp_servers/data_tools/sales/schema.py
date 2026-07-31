from __future__ import annotations

from typing import TypedDict


class SchemaResource(TypedDict):
    tables: list[str]
    columns: dict[str, list[str]]
    business_glossary: dict[str, str]


def get_schema_resource() -> SchemaResource:
    """판매 도메인의 View·컬럼·용어를 반환한다."""
    ...
