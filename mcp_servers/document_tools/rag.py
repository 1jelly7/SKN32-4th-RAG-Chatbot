from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from ingestion.embedding import embed
from ingestion.types import RawDocument
from mcp_servers.document_tools.faiss_store import FaissStore
from mcp_servers.document_tools.types import DocumentChunk

# 재기동 사이에 파일 재로드를 피하려고 프로세스 안에서 재사용하는 캐시입니다.
# (질문마다 임시 인덱스를 새로 만들던 이전 방식(DCC-008)을 대체합니다)
_store_cache: dict[str, FaissStore] = {}


def _load_persistent_store() -> tuple[FaissStore, str]:
    """scripts/ingest_documents.py(또는 rebuild_faiss_index.py)가 미리 만들어둔
    정식 FAISS 인덱스를 로드합니다. 질문마다 새로 만들지 않고, 같은 인덱스 파일이면
    프로세스 안에서 재사용합니다.
    """
    settings = get_settings()
    index_path = Path(settings.faiss_path) / "index.faiss"
    cache_key = str(index_path)

    cached = _store_cache.get(cache_key)
    if cached is not None:
        return cached, cached.index_version  # type: ignore[attr-defined]

    store = FaissStore(index_path)
    try:
        metadata = store.load()
    except FileNotFoundError as exc:
        raise RuntimeError(
            "정식 FAISS 인덱스가 없습니다. 먼저 `python scripts/ingest_documents.py`로 "
            "인덱싱을 실행하세요."
        ) from exc

    store.index_version = metadata["index_version"]  # type: ignore[attr-defined]
    _store_cache[cache_key] = store
    return store, store.index_version  # type: ignore[attr-defined]


def invalidate_store_cache() -> None:
    """재인덱싱 직후(rebuild_faiss_index.py) 프로세스 안 캐시를 비우기 위해 호출합니다."""
    _store_cache.clear()


async def retrieve(
    query: str,
    documents: list[RawDocument],
    top_k: int,
) -> list[DocumentChunk]:
    """정식(배치) FAISS 인덱스에서 검색하고, 문서 DB가 골라준 document_id로만 결과를
    좁힙니다.

    이전 구현은 질문마다 documents를 다시 청킹·임베딩해서 임시 인덱스를 만들고
    버렸습니다(DCC-008). 이 방식은 (1) 질문마다 재임베딩 비용이 들고 (2) 인덱스
    버전을 추적할 수 없어 cache freshness가 깨지는 문제가 있었습니다.

    이제는 scripts/ingest_documents.py가 미리 만들어둔 정식 인덱스를 그대로 검색하고,
    documents(문서 DB가 이번 질문과 관련 있다고 판단한 document_id 목록)로 결과를
    사후 필터링합니다. 이러면 인덱스 재사용이 되고, index_version도 안정적으로
    추적됩니다.
    """
    if not query.strip():
        raise ValueError("query가 비어 있습니다.")
    if top_k <= 0:
        raise ValueError("top_k는 1 이상이어야 합니다.")
    if not documents:
        return []

    allowed_document_ids = {d["document_id"] for d in documents}

    store, index_version = _load_persistent_store()

    query_vector = embed([query])[0]

    # documents로 필터링하면 후보가 줄어들 수 있으므로 넉넉히 더 가져옵니다.
    candidates = store.search(query_vector, top_k * 5)

    filtered = [c for c in candidates if c["document_id"] in allowed_document_ids]
    results = filtered[:top_k]

    # index_version을 각 chunk에 실어서, 상위(search.py/server.py)가 MCP envelope의
    # metadata에 담을 수 있게 합니다. 응답 스키마(DocumentChunk)에는 없는 필드라
    # 여기서는 별도 리스트로 함께 반환하지 않고, 모듈 레벨 함수로 조회 가능하게 합니다.
    return results


def get_last_index_version() -> str | None:
    """가장 최근에 로드된 정식 인덱스의 버전을 반환합니다. (server.py가 metadata에 포함시킬 때 사용)"""
    if not _store_cache:
        return None
    # 지금은 인덱스 경로가 하나뿐이라 가장 최근 로드된 것 하나만 반환합니다.
    store = next(iter(_store_cache.values()))
    return store.index_version  # type: ignore[attr-defined]
