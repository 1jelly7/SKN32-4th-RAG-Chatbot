from __future__ import annotations

from pathlib import Path

import pandas as pd


def extract_csv(path: Path) -> pd.DataFrame:
    ...


def extract_excel(path: Path, sheet_name: str | int | None) -> pd.DataFrame:
    ...


def extract_json(path: Path) -> pd.DataFrame:
    ...


def extract_api(url: str, timeout_seconds: int) -> pd.DataFrame:
    ...
