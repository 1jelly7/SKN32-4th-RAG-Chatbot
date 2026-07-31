"""판매 원천 데이터의 추출 책임을 둔다."""

from pathlib import Path

import pandas as pd


def extract_csv(path: Path) -> pd.DataFrame:
    """판매 CSV를 읽는다. 원본을 수정하지 않으며 이후 단계로 넘긴다."""
    ...
