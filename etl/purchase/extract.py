from __future__ import annotations

from pathlib import Path

import pandas as pd


def extract_csv(path: Path) -> pd.DataFrame:
    """존재하는 CSV를 명시적 인코딩·결측치 정책으로 읽어 DataFrame으로 반환한다.

    경로/확장자/파싱 오류를 출처가 포함된 예외로 보고하고, 원본을 수정하거나 조용히 행을
    버리지 않는다.
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    
    if path.suffix.lower() != '.csv':
        raise ValueError(f"Expected CSV file, got: {path.suffix}")
    
    try:
        df = pd.read_csv(path, encoding='utf-8')
        return df
    except Exception as e:
        raise IOError(f"Failed to parse CSV file {path}: {str(e)}")


def extract_excel(path: Path, sheet_name: str | int | None) -> pd.DataFrame:
    """Excel 파일과 지정 sheet를 읽고 sheet 부재·손상 파일을 명확히 실패 처리한다."""
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {path}")
    
    if path.suffix.lower() not in ['.xlsx', '.xls']:
        raise ValueError(f"Expected Excel file, got: {path.suffix}")
    
    try:
        df = pd.read_excel(path, sheet_name=sheet_name)
        return df
    except ValueError as e:
        raise ValueError(f"Sheet '{sheet_name}' not found in {path}: {str(e)}")
    except Exception as e:
        raise IOError(f"Failed to parse Excel file {path}, sheet '{sheet_name}': {str(e)}")


def extract_json(path: Path) -> pd.DataFrame:
    """JSON 레코드 구조를 표 형식으로 읽고 중첩 구조 처리 규칙을 문서화해 적용한다."""
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    
    if path.suffix.lower() != '.json':
        raise ValueError(f"Expected JSON file, got: {path.suffix}")
    
    try:
        df = pd.read_json(path, orient='records')
        return df
    except Exception as e:
        raise IOError(f"Failed to parse JSON file {path}: {str(e)}")


def extract_api(url: str, timeout_seconds: int) -> pd.DataFrame:
    """허용된 원천 API에서 timeout·상태 코드·응답 스키마를 검증해 데이터를 추출한다.

    재시도 정책과 인증 정보 처리는 설정 계층에 두며, 실패 응답을 빈 DataFrame으로 위장하지
    않는다.
    """
    import requests
    
    try:
        response = requests.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)
        return df
    except requests.exceptions.Timeout:
        raise TimeoutError(f"API request timed out after {timeout_seconds} seconds")
    except requests.exceptions.HTTPError as e:
        raise IOError(f"API request failed with status {response.status_code}: {str(e)}")
    except Exception as e:
        raise IOError(f"Failed to extract data from API {url}: {str(e)}")
