from __future__ import annotations

from typing import TypedDict


class ValidationReport(TypedDict):
    is_valid: bool
    invalid_row_count: int
    errors: list[str]


class LoadResult(TypedDict):
    table: str
    inserted_count: int
    updated_count: int


class PipelineResult(TypedDict):
    source_path: str
    validation: ValidationReport
    load: LoadResult | None
