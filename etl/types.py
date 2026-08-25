"""소유 도메인이 확정되지 않은 범용 ETL 스켈레톤의 결과 타입."""

from __future__ import annotations

from typing import TypedDict


class ValidationReport(TypedDict):
    """범용 검증 결과와 오류 요약."""

    is_valid: bool
    invalid_row_count: int
    errors: list[str]


class LoadResult(TypedDict):
    """범용 UPSERT의 table별 삽입·갱신 수."""

    table: str
    inserted_count: int
    updated_count: int


class PipelineResult(TypedDict):
    """원천부터 검증·선택적 적재까지의 범용 결과."""

    source_path: str
    validation: ValidationReport
    load: LoadResult | None
