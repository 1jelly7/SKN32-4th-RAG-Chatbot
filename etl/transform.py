from __future__ import annotations

from typing import Any

import pandas as pd


def transform(
    frame: pd.DataFrame,
    column_mapping: dict[str, str] | None = None,
    type_mapping: dict[str, Any] | None = None,
) -> pd.DataFrame:
    ...
