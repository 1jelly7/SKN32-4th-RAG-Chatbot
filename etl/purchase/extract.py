"""구매 원천 데이터의 추출 책임을 둔다."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def extract_csv(path: Path) -> pd.DataFrame:
    """구매 CSV를 읽는다. 원본을 수정하지 않으며 이후 단계로 넘긴다."""
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    if path.suffix.lower() != ".csv":
        raise ValueError(f"Expected CSV file, got: {path.suffix}")
    return pd.read_csv(path)


def extract_excel_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    """구매 워크북(xlsx)의 지정 시트를 읽는다.

    원천 헤더(PascalCase, 예: 'PO_ID')를 스키마(schema.py)의 소문자 컬럼명
    규칙에 맞춰 정규화한다(etl/sales/extract.py와 동일 패턴 — 원천이
    'Word_Word' 형태라 소문자화만으로 목표 컬럼명이 정확히 나온다). 값
    자체는 수정하지 않는다.
    """
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {path}")
    frame = pd.read_excel(path, sheet_name=sheet_name)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    return frame
