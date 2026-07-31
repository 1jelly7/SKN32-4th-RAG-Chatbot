from ingestion.types import DocumentChunk, RawDocument


def chunk_document(
    document: RawDocument,
    chunk_size: int,
    chunk_overlap: int,
) -> list[DocumentChunk]:
    """문서 문맥을 보존하면서 크기 제한과 overlap을 만족하는 chunk 목록을 만든다.

    제목/섹션/문단 경계 우선 분할, 빈 chunk 제거, 안정적인 ``chunk_id`` 부여가 필요하다.
    원본 document_id와 file_path metadata를 모든 chunk에 복사하고, chunk_size·overlap의
    불가능한 조합은 명확히 거절한다.
    """
    ...
