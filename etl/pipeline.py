"""범용 CSV ETL 단계를 조합하려는 미구현 배치 진입점."""

from pathlib import Path

from etl.types import PipelineResult


def run_csv_pipeline(
    path: Path,
    table: str,
    required_columns: list[str],
) -> PipelineResult:
    """CSV ETL의 extract → transform → validate → load 순서를 오케스트레이션한다.

    단계별 입력/출력 개수와 오류를 기록하고, validation.is_valid가 false면 load를 호출하지
    않은 채 ``load=None``인 결과를 반환한다. 예외에는 source path와 단계명을 포함하되
    원본 민감 데이터는 로그에 기록하지 않는다.
    """
    # TODO(contract clarification): 실제 소유 도메인을 확정한 뒤 extract→transform→
    # validate→load 순서를 구현한다. 검증 실패는 load=None으로 중단하고 API/Agent에서
    # 호출하지 않는 fake orchestration test가 완료 조건이다.
    ...
