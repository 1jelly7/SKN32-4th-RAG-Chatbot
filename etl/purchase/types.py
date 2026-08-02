"""구매 ETL 단계 사이의 검증·적재·pipeline 결과 계약."""

from __future__ import annotations

from typing import TypedDict


class ValidationReport(TypedDict):
    """구매 검증 결과와 오류 요약."""

    is_valid: bool
    invalid_row_count: int
    errors: list[str]


class LoadResult(TypedDict):
    """구매 UPSERT의 table별 삽입·갱신 수."""

    table: str
    inserted_count: int
    updated_count: int


class PipelineResult(TypedDict):
    """구매 원천부터 검증·선택적 적재까지의 결과."""

    source_path: str
    validation: ValidationReport
    load: LoadResult | None
