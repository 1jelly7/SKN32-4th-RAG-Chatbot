"""구매 적재 전 schema와 행 품질을 판정하는 미구현 검증 경계."""

import pandas as pd

from etl.purchase.types import ValidationReport


def validate(frame: pd.DataFrame, required_columns: list[str]) -> ValidationReport:
    """적재 전 스키마·필수값·형식·참조/코드 규칙을 검사해 구조화 보고서를 만든다.

    누락 컬럼과 각 invalid row의 이유를 식별 가능한 오류 메시지로 모으고, 오류 행을
    조용히 제거하지 않는다. ``is_valid``는 오류 임계치 정책에 따라 결정되며 load 단계는
    false일 때 실행되지 않아야 한다.
    """
    # TODO(implementation): 누락 컬럼과 행별 필수값·형식·코드 오류를 ValidationReport로
    # 수집한다. invalid row를 삭제하지 않으며 is_valid=False이면 pipeline이 load를
    # 호출하지 않는 fake 회귀가 완료 조건이다.
    ...
