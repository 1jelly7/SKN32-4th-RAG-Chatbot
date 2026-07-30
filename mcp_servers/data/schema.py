from __future__ import annotations

from typing import TypedDict


class SchemaResource(TypedDict):
    allowed_tables: list[str]
    allowed_columns: dict[str, list[str]]
    business_glossary: dict[str, str]


def get_schema_resource() -> SchemaResource:
    ...
