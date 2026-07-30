import pandas as pd

from etl.types import ValidationReport


def validate(frame: pd.DataFrame, required_columns: list[str]) -> ValidationReport:
    ...
