from pathlib import Path

from etl.types import PipelineResult


def run_csv_pipeline(
    path: Path,
    table: str,
    required_columns: list[str],
) -> PipelineResult:
    ...
