from __future__ import annotations

from typing import TypedDict


class SchemaResource(TypedDict):
    tables: list[str]
    columns: dict[str, list[str]]
    business_glossary: dict[str, str]


def get_schema_resource() -> SchemaResource:
    """Text2SQL에 재무 테이블·컬럼·업무 용어를 제공하는 MCP Resource를 만든다.

    반환 구조는 LLM이 임의 스키마를 추측하지 않도록 충분히 구체적이되 실제 연결 정보는
    포함하지 않는다.
    """
    ...
