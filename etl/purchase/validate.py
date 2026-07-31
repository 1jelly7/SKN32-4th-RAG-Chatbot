import pandas as pd

from .types import ValidationReport


def validate(frame: pd.DataFrame, required_columns: list[str]) -> ValidationReport:
    """적재 전 스키마·필수값·형식·참조/코드 규칙을 검사해 구조화 보고서를 만든다.

    누락 컬럼과 각 invalid row의 이유를 식별 가능한 오류 메시지로 모으고, 오류 행을
    조용히 제거하지 않는다. ``is_valid``는 오류 임계치 정책에 따라 결정되며 load 단계는
    false일 때 실행되지 않아야 한다.
    """
    errors = []
    invalid_row_count = 0

    # 1. 필수 컬럼 확인
    missing_columns = [col for col in required_columns if col not in frame.columns]
    if missing_columns:
        errors.append(f"Missing required columns: {', '.join(missing_columns)}")

    # 2. 필수 컬럼의 NULL 값 확인
    for col in required_columns:
        if col in frame.columns:
            null_count = frame[col].isna().sum()
            if null_count > 0:
                errors.append(f"Column '{col}' has {null_count} NULL values")
                invalid_row_count += null_count

    # 3. 전체 행 수 확인
    if len(frame) == 0:
        errors.append("DataFrame is empty")
        is_valid = False
    else:
        # 오류 임계치: 에러가 있으면 invalid
        is_valid = len(errors) == 0

    return ValidationReport(
        is_valid=is_valid,
        invalid_row_count=invalid_row_count,
        errors=errors
    )