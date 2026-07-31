<<<<<<< HEAD
"""
RawDocument를 문맥을 보존하는 chunk로 분할합니다.
"""

from __future__ import annotations

=======
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0
from ingestion.types import DocumentChunk, RawDocument


def chunk_document(
    document: RawDocument,
    chunk_size: int,
    chunk_overlap: int,
) -> list[DocumentChunk]:
    """문서 문맥을 보존하면서 크기 제한과 overlap을 만족하는 chunk 목록을 만든다.

<<<<<<< HEAD
    - loaders.py가 PDF 페이지 사이에 넣어둔 '\\f'(form feed)를 기준으로 먼저 페이지를
      나누고, 페이지 안에서는 문단(빈 줄) 경계를 우선으로 chunk_size를 넘지 않게 모읍니다.
    - 각 chunk의 metadata에 원본 document_id, file_path, page(1부터 시작)를 복사합니다.
    - 빈 chunk(공백만 있는 경우)는 제거합니다.
    - chunk_size <= 0 이거나 chunk_overlap이 chunk_size 이상이면 잘못된 조합이므로
      ValueError로 명확히 거절합니다.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size는 0보다 커야 합니다.")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap은 0 이상이면서 chunk_size보다 작아야 합니다.")

    pages = document["content"].split("\f")

    chunks: list[DocumentChunk] = []
    chunk_index = 0

    for page_number, page_text in enumerate(pages, start=1):
        for piece in _split_text(page_text, chunk_size, chunk_overlap):
            if not piece.strip():
                continue

            chunk_id = f"{document['document_id']}-{chunk_index}"
            metadata = dict(document.get("metadata", {}))
            metadata["document_id"] = document["document_id"]
            metadata["file_path"] = document["path"]
            metadata["title"] = document["title"]
            metadata["page"] = page_number

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": document["document_id"],
                    "content": piece.strip(),
                    "metadata": metadata,
                }
            )
            chunk_index += 1

    return chunks


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """문단(빈 줄) 경계를 우선으로 사용하고, 문단이 chunk_size보다 크면 강제로 자릅니다."""

    paragraphs = [p for p in text.split("\n\n") if p.strip()]

    if not paragraphs:
        # 문단 구분이 없는 텍스트는 문자 단위로 슬라이딩 윈도우로 자릅니다.
        return _slide_window(text, chunk_size, chunk_overlap)

    pieces: list[str] = []
    buffer = ""

    for paragraph in paragraphs:
        candidate = f"{buffer}\n\n{paragraph}" if buffer else paragraph

        if len(candidate) <= chunk_size:
            buffer = candidate
            continue

        # 지금까지 모은 buffer를 하나의 chunk로 확정합니다.
        if buffer:
            pieces.append(buffer)

        if len(paragraph) > chunk_size:
            # 문단 하나가 chunk_size보다 크면 그 문단만 슬라이딩 윈도우로 강제 분할합니다.
            pieces.extend(_slide_window(paragraph, chunk_size, chunk_overlap))
            buffer = ""
        else:
            buffer = paragraph

    if buffer:
        pieces.append(buffer)

    return pieces


def _slide_window(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """문자 단위 슬라이딩 윈도우로 텍스트를 자릅니다."""

    step = chunk_size - chunk_overlap
    pieces = []
    for start in range(0, len(text), step):
        piece = text[start : start + chunk_size]
        if piece.strip():
            pieces.append(piece)
        if start + chunk_size >= len(text):
            break
    return pieces
=======
    제목/섹션/문단 경계 우선 분할, 빈 chunk 제거, 안정적인 ``chunk_id`` 부여가 필요하다.
    원본 document_id와 file_path metadata를 모든 chunk에 복사하고, chunk_size·overlap의
    불가능한 조합은 명확히 거절한다.
    """
    ...
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0
