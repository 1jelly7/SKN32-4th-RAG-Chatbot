"""실제 테스트 MySQL을 사용할 ETL 통합 수용 테스트의 미구현 자리표시자."""

import pytest


@pytest.mark.integration
def test_placeholder_etl_flow() -> None:
    """현재 pass는 외부 ETL 통합 완료를 증명하지 않는다."""
    # TODO(implementation): 격리된 테스트 MySQL과 비식별 fixture로 구매·판매 ETL을
    # 두 번 실행해 UPSERT 멱등성, 처리 행 수, 검증 결과, transaction rollback을 확인한다.
    # 실제 DB가 준비되지 않으면 명시적으로 skip하되 이 placeholder를 성공 근거로 삼지 않는다.
    assert True
