"""소유자 결정 전 보존하는 legacy finance ETL 결과 타입."""

from __future__ import annotations

from typing import TypedDict


class ValidationReport(TypedDict):
    """legacy finance 검증 결과와 오류 요약."""

    is_valid: bool
    invalid_row_count: int
    errors: list[str]


class LoadResult(TypedDict):
    """legacy finance 적재 결과."""

    table: str
    inserted_count: int
    updated_count: int


class PipelineResult(TypedDict):
    """legacy finance pipeline 결과."""

    source_path: str
    validation: ValidationReport
    load: LoadResult | None
