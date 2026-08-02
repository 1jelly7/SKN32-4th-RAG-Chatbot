"""구매 ETL transform의 최소 중복 제거 회귀 테스트.

정식 purchase/sales ETL 통합 완료를 증명하지 않으며 외부 MySQL을 사용하지 않는다.
"""

import pandas as pd

from etl.purchase.transform import transform


def test_transform_deduplicates() -> None:
    """동일 행 재처리가 중복 행을 늘리지 않는 최소 변환 계약을 고정한다."""
    assert len(transform(pd.DataFrame({"id": [1, 1]}))) == 1
