from pathlib import Path

from ingestion.types import RawDocument


def load_documents(path: Path) -> list[RawDocument]:
    """입력 파일 또는 디렉터리에서 지원 형식(PDF/TXT/Markdown)만 안정적으로 수집한다.

    경로를 정렬해 재현 가능한 순서를 만들고, 숨김/지원하지 않는 파일의 처리 정책과 개별
    파일 오류 보고 방식을 명시한다. 문서 내용은 이후 metadata와 ACL 설정을 위해 보존한다.
    """
    ...


def load_pdf(path: Path) -> RawDocument:
    """PDF의 페이지 순서를 보존해 텍스트와 기본 출처 metadata를 RawDocument로 만든다."""
    ...


def load_text(path: Path) -> RawDocument:
    """인코딩을 안전하게 판별해 일반 텍스트를 읽고 안정된 document_id를 생성한다."""
    ...


def load_markdown(path: Path) -> RawDocument:
    """Markdown 제목/헤더 정보를 title·metadata에 반영해 문서를 읽는다."""
    ...
