"""
프로젝트 docs 폴더에 한정된 안전한 파일 시스템 Tool을 제공합니다.
"""

# 파일 경로 처리를 위해 Path를 가져옵니다.
from pathlib import Path

# PDF 텍스트 추출을 위해 pypdf를 가져옵니다.
from pypdf import PdfReader


# 허용된 루트 폴더 안의 경로인지 검사합니다.
def _safe_path(base_dir: Path, filename: str) -> Path:
    """경로 탈출 공격을 방지하면서 파일 경로를 반환합니다."""

    # 기준 폴더의 절대 경로를 계산합니다.
    base = base_dir.resolve()

    # 사용자 파일명을 기준 폴더와 결합한 뒤 절대 경로로 변환합니다.
    target = (base / filename).resolve()

    # 대상 경로가 기준 폴더 내부가 아니면 접근을 거부합니다.
    if base not in target.parents and target != base:
        raise ValueError("docs 폴더 밖의 경로에는 접근할 수 없습니다.")

    # 검증이 끝난 경로를 반환합니다.
    return target


# docs 폴더의 파일 목록을 반환합니다.
def list_doc_files(base_dir: Path) -> list[str]:
    """docs 폴더의 파일명을 반환합니다."""

    # 폴더가 없으면 생성합니다.
    base_dir.mkdir(parents=True, exist_ok=True)

    # 실제 파일만 정렬하여 파일명 목록으로 반환합니다.
    return [path.name for path in sorted(base_dir.iterdir()) if path.is_file()]


# docs 폴더의 문서 파일을 읽습니다.
def read_doc_file(base_dir: Path, filename: str) -> str:
    """검증된 문서 파일의 내용을 텍스트로 읽습니다. PDF는 자동으로 텍스트를 추출합니다."""

    # 안전한 파일 경로를 계산합니다.
    target = _safe_path(base_dir, filename)

    # 파일이 없으면 오류를 발생시킵니다.
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filename}")

    # PDF는 페이지별 텍스트를 추출해 이어 붙입니다.
    if target.suffix.lower() == ".pdf":
        reader = PdfReader(str(target))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    # 그 외 파일은 UTF-8 텍스트로 그대로 반환합니다.
    return target.read_text(encoding="utf-8")
