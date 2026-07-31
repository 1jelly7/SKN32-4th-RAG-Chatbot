"""판매 데이터의 정규화·중복 제거 규칙을 둔다."""

from typing import Any

import pandas as pd


def transform(
    frame: pd.DataFrame,
    column_mapping: dict[str, str] | None = None,
    type_mapping: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """판매 스키마를 정규화한 새 프레임을 반환한다."""
    result = frame.copy()
    if column_mapping:
        result = result.rename(columns=column_mapping)
    if type_mapping:
        for column, dtype in type_mapping.items():
            if column in result:
                result[column] = result[column].astype(dtype)
    return result.drop_duplicates().reset_index(drop=True)
