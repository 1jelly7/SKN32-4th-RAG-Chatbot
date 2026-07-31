<<<<<<< HEAD
"""
문서 DB가 알려준 경로(또는 디렉터리)에서 지원 형식의 문서만 읽어
RawDocument로 변환합니다.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader

from ingestion.types import RawDocument

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".markdown"}


def _make_document_id(path: Path) -> str:
    """경로 문자열의 SHA-256 앞부분으로 안정적인 document_id를 만듭니다.

    같은 경로는 항상 같은 id를 만들어서, 재인덱싱해도 document_id가 바뀌지 않게 합니다.
    """
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
    return f"doc-{digest[:16]}"

=======
from pathlib import Path

from ingestion.types import RawDocument

>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0

def load_documents(path: Path) -> list[RawDocument]:
    """문서 DB에서 확인한 파일 또는 디렉터리 경로의 지원 문서만 수집한다.

<<<<<<< HEAD
    경로를 정렬해 재현 가능한 순서를 만들고, 숨김/지원하지 않는 파일은 조용히
    건너뜁니다(개별 파일 오류는 로드 자체를 막지 않되, 어떤 파일이 실패했는지는
    호출자가 확인할 수 있도록 예외 메시지에 파일명을 포함합니다).
    임의 입력 경로나 문서 DB에 없는 경로는 이 함수 스스로 검증하지 않습니다 -
    호출자(예: document_db 조회 결과)가 이미 검증된 경로만 넘겨야 합니다.
    """

    if path.is_file():
        candidates = [path]
    else:
        # 디렉터리인 경우 하위 파일을 정렬해 재현 가능한 순서로 만듭니다.
        candidates = sorted(
            p for p in path.iterdir() if p.is_file() and not p.name.startswith(".")
        )

    documents: list[RawDocument] = []
    for candidate in candidates:
        suffix = candidate.suffix.casefold()
        if suffix not in SUPPORTED_SUFFIXES:
            continue

        if suffix == ".pdf":
            documents.append(load_pdf(candidate))
        elif suffix in {".md", ".markdown"}:
            documents.append(load_markdown(candidate))
        else:
            documents.append(load_text(candidate))

    return documents
=======
    경로를 정렬해 재현 가능한 순서를 만들고, 숨김/지원하지 않는 파일의 처리 정책과 개별
    파일 오류 보고 방식을 명시한다. 임의 입력 경로나 문서 DB에 없는 경로를 사용하지 않는다.
    """
    ...
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0


def load_pdf(path: Path) -> RawDocument:
    """PDF의 페이지 순서를 보존해 텍스트와 기본 출처 metadata를 RawDocument로 만든다."""
<<<<<<< HEAD

    reader = PdfReader(str(path))

    # 페이지 경계를 유지하기 위해 페이지 사이에 명시적인 구분자를 넣습니다.
    # (chunking 단계에서 페이지 번호를 복원할 때 이 구분자를 기준으로 나눕니다)
    page_texts = [page.extract_text() or "" for page in reader.pages]
    content = "\f".join(page_texts)  # \f(form feed)를 페이지 구분자로 사용

    return {
        "document_id": _make_document_id(path),
        "path": str(path),
        "title": path.stem,
        "content": content,
        "metadata": {"source_type": "pdf", "page_count": len(reader.pages)},
    }
=======
    ...
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0


def load_text(path: Path) -> RawDocument:
    """인코딩을 안전하게 판별해 일반 텍스트를 읽고 안정된 document_id를 생성한다."""
<<<<<<< HEAD

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # UTF-8이 아니면 흔한 한국어 인코딩(cp949)도 시도해봅니다.
        content = path.read_text(encoding="cp949", errors="replace")

    return {
        "document_id": _make_document_id(path),
        "path": str(path),
        "title": path.stem,
        "content": content,
        "metadata": {"source_type": "text"},
    }
=======
    ...
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0


def load_markdown(path: Path) -> RawDocument:
    """Markdown 제목/헤더 정보를 title·metadata에 반영해 문서를 읽는다."""
<<<<<<< HEAD

    content = path.read_text(encoding="utf-8")

    # 첫 번째 '# 제목' 헤더를 찾으면 그걸 title로 사용하고, 없으면 파일명을 씁니다.
    title = path.stem
    headers: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            header_text = stripped.lstrip("#").strip()
            headers.append(header_text)
            if title == path.stem and stripped.startswith("# "):
                title = header_text

    return {
        "document_id": _make_document_id(path),
        "path": str(path),
        "title": title,
        "content": content,
        "metadata": {"source_type": "markdown", "headers": headers},
    }
=======
    ...
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0
