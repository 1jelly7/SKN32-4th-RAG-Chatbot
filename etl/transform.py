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
    ...
