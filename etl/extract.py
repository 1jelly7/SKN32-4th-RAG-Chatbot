"""도메인 소유가 확정되지 않은 범용 ETL extract 스켈레톤."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def extract_csv(path: Path) -> pd.DataFrame:
    """존재하는 CSV를 명시적 인코딩·결측치 정책으로 읽어 DataFrame으로 반환한다.

    경로/확장자/파싱 오류를 출처가 포함된 예외로 보고하고, 원본을 수정하거나 조용히 행을
    버리지 않는다.
    """
    # TODO(contract clarification): 이 범용 경계를 채택할 도메인과 인코딩·결측치 정책을
    # 확정한 뒤 구현한다. 빈 frame fallback으로 원천 오류를 숨기지 않는다.
    ...


def extract_excel(path: Path, sheet_name: str | int | None) -> pd.DataFrame:
    """Excel 파일과 지정 sheet를 읽고 sheet 부재·손상 파일을 명확히 실패 처리한다."""
    # TODO(implementation): 채택 시 workbook/sheet 오류를 구분하는 fixture test와 함께
    # 원본 보존 extract를 구현한다.
    ...


def extract_json(path: Path) -> pd.DataFrame:
    """JSON 레코드 구조를 표 형식으로 읽고 중첩 구조 처리 규칙을 문서화해 적용한다."""
    # TODO(contract clarification): 허용 record/nested JSON schema를 먼저 정의한다.
    ...


def extract_api(url: str, timeout_seconds: int) -> pd.DataFrame:
    """허용된 원천 API에서 timeout·상태 코드·응답 스키마를 검증해 데이터를 추출한다.

    재시도 정책과 인증 정보 처리는 설정 계층에 두며, 실패 응답을 빈 DataFrame으로 위장하지
    않는다.
    """
    # TODO(contract clarification): 원천 allowlist, 인증 주입, timeout/retry 정책이 없다.
    # 확정 전 임의 URL 호출을 구현하지 않는다.
    ...
