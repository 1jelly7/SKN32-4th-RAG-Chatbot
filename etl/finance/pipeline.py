from pathlib import Path

from etl.finance.types import PipelineResult


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
    ...
