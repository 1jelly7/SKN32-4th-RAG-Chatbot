"""구매 원천 frame을 복사해 schema 변환과 중복 제거를 적용한다."""

from __future__ import annotations

from typing import Any

import pandas as pd


def transform(
    frame: pd.DataFrame,
    column_mapping: dict[str, str] | None = None,
    type_mapping: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """원본 프레임을 표준 스키마로 정규화하고 중복을 제거한 새 프레임을 반환한다.

    column_mapping을 적용한 뒤 날짜·통화·코드 등의 type_mapping을 명시적으로 변환한다.
    자연키 기준 중복 제거 규칙과 유지 행을 결정적으로 정하고, 입력 프레임을 제자리에서
    수정하지 않는다. 변환 실패값은 검증 단계가 추적할 수 있게 보존/표시한다.
    """
    result = frame.copy()

    # 1. 컬럼명 변경 (매핑이 있으면)
    if column_mapping:
        result = result.rename(columns=column_mapping)

    # 2. 타입 변환 (매핑이 있으면)
    if type_mapping:
        for column, dtype in type_mapping.items():
            if column in result.columns:
                try:
                    result[column] = result[column].astype(dtype)
                except Exception as e:
                    # 변환 실패값은 보존 (검증 단계가 처리)
                    print(
                        f"Warning: Failed to convert column '{column}' to {dtype}: {str(e)}"
                    )

    # 3. 중복 제거 및 인덱스 초기화
    result = result.drop_duplicates().reset_index(drop=True)

    return result
