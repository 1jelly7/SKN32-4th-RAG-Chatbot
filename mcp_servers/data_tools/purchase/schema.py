"""구매 Text2SQL에 허용할 schema와 업무 용어의 미구현 Resource."""

from __future__ import annotations

from typing import TypedDict


class SchemaResource(TypedDict):
    """구매 Text2SQL이 사용할 허용 schema와 업무 용어."""

    tables: list[str]
    columns: dict[str, list[str]]
    business_glossary: dict[str, str]


def get_schema_resource() -> SchemaResource:
    """Text2SQL에 구매 테이블·컬럼·업무 용어를 제공하는 MCP Resource를 만든다.

    반환 구조는 LLM이 임의 스키마를 추측하지 않도록 충분히 구체적이되 실제 연결 정보는
    포함하지 않는다.
    """
    # TODO(implementation): database/purchase 소유 schema와 용어집에서 허용 table/column만
    # 반환한다. 연결 정보·민감 컬럼은 제외하고 실제 DDL과 일치하는 contract test를
    # 추가해야 한다.
    ...
