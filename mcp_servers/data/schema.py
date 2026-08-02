"""정책 allowlist 기반 범용 Data MCP의 미구현 schema Resource."""

from __future__ import annotations

from typing import TypedDict


class SchemaResource(TypedDict):
    """범용 Text2SQL에 허용할 table·column·용어 allowlist."""

    allowed_tables: list[str]
    allowed_columns: dict[str, list[str]]
    business_glossary: dict[str, str]


def get_schema_resource() -> SchemaResource:
    """Text2SQL에 허용된 테이블·컬럼·업무 용어만 제공하는 MCP Resource를 만든다.

    정책 YAML/관리된 설정에서 읽고 민감 컬럼·내부 테이블은 제외한다. 반환 구조는 LLM이
    임의 스키마를 추측하지 않도록 충분히 구체적이되 실제 연결 정보는 포함하지 않는다.
    """
    # TODO(contract clarification): 정식 purchase/sales schema와 이 범용 정책 경계의
    # 관계 및 정책 저장 위치를 소유자와 확정한다. 확정 전에는 임의 테이블을 기본
    # 허용하거나 운영 스키마를 추측하지 않는다.
    ...
