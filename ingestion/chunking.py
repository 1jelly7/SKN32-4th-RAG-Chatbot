from ingestion.types import DocumentChunk, RawDocument


def chunk_document(
    document: RawDocument,
    chunk_size: int,
    chunk_overlap: int,
) -> list[DocumentChunk]:
    ...
