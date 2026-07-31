"""판매 extract → transform → validate → load 파이프라인 진입점."""

from pathlib import Path

from etl.sales.types import PipelineResult


def run_csv_pipeline(path: Path, table: str, required_columns: list[str]) -> PipelineResult:
    """판매 ETL 단계를 순서대로 실행한다."""
    ...
