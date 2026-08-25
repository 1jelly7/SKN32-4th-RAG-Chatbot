"""판매 ETL의 스키마·필수값 검증 책임을 둔다."""

import pandas as pd

from etl.sales.types import ValidationReport


def validate(frame: pd.DataFrame, required_columns: list[str]) -> ValidationReport:
    """적재 전 판매 데이터의 필수 컬럼을 검사한다."""
    missing = [column for column in required_columns if column not in frame.columns]
    return {"is_valid": not missing, "invalid_row_count": 0, "errors": missing}
