"""구매 ETL의 스키마·필수값 검증 책임을 둔다."""

from __future__ import annotations

import pandas as pd

from etl.purchase.types import ValidationReport


def validate(frame: pd.DataFrame, required_columns: list[str]) -> ValidationReport:
    """적재 전 구매 데이터의 필수 컬럼과 NULL 여부를 검사한다.

    누락 컬럼이 있으면 즉시 실패로 표시하고, 존재하는 필수 컬럼이라도 NULL이
    섞여 있으면 오류로 집계한다(sales의 validate()보다 엄격 — 하향 통일하지
    않는다). 오류 행을 조용히 제거하지 않는다.
    """
    errors: list[str] = []
    invalid_row_count = 0

    missing_columns = [col for col in required_columns if col not in frame.columns]
    if missing_columns:
        errors.append(f"Missing required columns: {', '.join(missing_columns)}")

    for col in required_columns:
        if col in frame.columns:
            null_count = int(frame[col].isna().sum())
            if null_count > 0:
                errors.append(f"Column '{col}' has {null_count} NULL values")
                invalid_row_count += null_count

    if len(frame) == 0:
        errors.append("DataFrame is empty")

    is_valid = len(errors) == 0
    return ValidationReport(is_valid=is_valid, invalid_row_count=invalid_row_count, errors=errors)
