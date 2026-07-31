from __future__ import annotations

from typing import TypedDict


class SchemaResource(TypedDict):
    allowed_tables: list[str]
    allowed_columns: dict[str, list[str]]
    business_glossary: dict[str, str]


def get_schema_resource() -> SchemaResource:
    """Text2SQL에 허용된 테이블·컬럼·업무 용어만 제공하는 MCP Resource를 만든다.

    정책 YAML/관리된 설정에서 읽고 민감 컬럼·내부 테이블은 제외한다. 반환 구조는 LLM이
    임의 스키마를 추측하지 않도록 충분히 구체적이되 실제 연결 정보는 포함하지 않는다.
    """
    ...
