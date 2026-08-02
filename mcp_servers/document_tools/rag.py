"""조회된 문서 후보만 임시 FAISS 인덱스로 검색하는 RAG 실행 경계."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from ingestion.chunking import chunk_document
from ingestion.embedding import embed
from ingestion.index import build_index
from ingestion.types import RawDocument
from mcp_servers.document_tools.faiss_store import FaissStore
from mcp_servers.document_tools.types import DocumentChunk

CHUNK_SIZE = 500
CHUNK_OVERLAP = 80


async def retrieve(
    query: str,
    documents: list[RawDocument],
    top_k: int,
) -> list[DocumentChunk]:
    """문서 DB 경로에서 읽은 문서만 대상으로 embedding 검색과 rerank를 수행한다.

    query/top_k와 문서 목록을 검증하고, embedding 모델·인덱스 차원·버전을 호환성
    검사한다. rerank는 후보의 원본 식별자와 score를 보존하고 내부 file_path는
    응답에서 제거한다.

    구현 메모: document_db가 매 질문마다 다른 후보 문서 집합을 돌려줄 수 있으므로,
    여기서는 그 문서들만 대상으로 임시 FAISS 인덱스를 그때그때 만들어 검색합니다.
    (전체 문서에 대한 상시 인덱스는 scripts/rebuild_faiss_index.py가 배치로
    data/faiss/에 미리 만들어두고, 그건 향후 "사전 인덱스 재사용" 최적화에 씁니다.)
    """

    if not query.strip():
        raise ValueError("query가 비어 있습니다.")
    if top_k <= 0:
        raise ValueError("top_k는 1 이상이어야 합니다.")
    if not documents:
        return []

    all_chunks = []
    for document in documents:
        all_chunks.extend(chunk_document(document, CHUNK_SIZE, CHUNK_OVERLAP))

    if not all_chunks:
        return []

    vectors = embed([chunk["content"] for chunk in all_chunks])
    query_vector = embed([query])[0]

    # 이번 질문 범위의 문서만으로 임시 인덱스를 만듭니다. (dimension은 embed()가 항상
    # 동일하게 만들어주므로 호환성 문제는 벡터 길이가 다를 때뿐이며, embed()가 그 계약을
    # 보장합니다)
    tmp_dir = Path(tempfile.mkdtemp(prefix="rag_query_index_"))
    try:
        build_index(all_chunks, vectors, tmp_dir)
        store = FaissStore(tmp_dir / "index.faiss")
        store.load()
        return store.search(query_vector, top_k)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
