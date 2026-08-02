"""구매 배치가 허용된 원천을 DataFrame으로 읽는 미구현 extract 경계."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def extract_csv(path: Path) -> pd.DataFrame:
    """존재하는 CSV를 명시적 인코딩·결측치 정책으로 읽어 DataFrame으로 반환한다.

    경로/확장자/파싱 오류를 출처가 포함된 예외로 보고하고, 원본을 수정하거나 조용히 행을
    버리지 않는다.
    """
    # TODO(implementation): 존재·확장자·인코딩을 검증해 원본 행을 보존한다. 손상 파일과
    # 파싱 오류를 빈 frame으로 숨기지 않는 fixture test가 완료 조건이다.
    ...


def extract_excel(path: Path, sheet_name: str | int | None) -> pd.DataFrame:
    """Excel 파일과 지정 sheet를 읽고 sheet 부재·손상 파일을 명확히 실패 처리한다."""
    # TODO(implementation): 지정 sheet 존재와 workbook 손상을 구분하고 원본을 수정하지
    # 않은 DataFrame을 반환한다. sheet 누락·손상 fixture를 검증한다.
    ...


def extract_json(path: Path) -> pd.DataFrame:
    """JSON 레코드 구조를 표 형식으로 읽고 중첩 구조 처리 규칙을 문서화해 적용한다."""
    # TODO(contract clarification): 허용 JSON record/nested 구조를 확정한 뒤 비정상
    # schema를 명시적으로 거절하고 행을 조용히 유실하지 않는다.
    ...


def extract_api(url: str, timeout_seconds: int) -> pd.DataFrame:
    """허용된 원천 API에서 timeout·상태 코드·응답 스키마를 검증해 데이터를 추출한다.

    재시도 정책과 인증 정보 처리는 설정 계층에 두며, 실패 응답을 빈 DataFrame으로 위장하지
    않는다.
    """
    # TODO(contract clarification): 구매 원천 API allowlist, 인증 주입, retry 정책이
    # 문서에 정의되지 않았다. 확정 후 timeout·HTTP 상태·응답 schema를 구분한다.
    ...
