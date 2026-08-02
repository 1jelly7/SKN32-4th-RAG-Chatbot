"""판매 원천 데이터의 추출 책임을 둔다."""

from pathlib import Path

import pandas as pd


def extract_csv(path: Path) -> pd.DataFrame:
    """판매 CSV를 읽는다. 원본을 수정하지 않으며 이후 단계로 넘긴다."""
    return pd.read_csv(path)


def extract_excel_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    """판매 워크북(xlsx)의 지정 시트를 읽는다.

    원천 CSV가 아직 준비되지 않은 소스(예: ERP_Sales_Data_Full.xlsx)에 사용한다.
    반환값은 extract_csv와 동일하게 원본 그대로의 DataFrame이며, 이후 단계
    (transform/validate/load)는 두 추출 방식을 구분하지 않고 동일하게 다룬다.

    헤더만 스키마(schema.py)의 소문자 컬럼명 규칙에 맞춰 정규화한다
    (원본 워크북 헤더는 'Customer_ID'처럼 대문자 스네이크 케이스다). 값 자체는
    수정하지 않는다.
    """
    frame = pd.read_excel(path, sheet_name=sheet_name)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    return frame
