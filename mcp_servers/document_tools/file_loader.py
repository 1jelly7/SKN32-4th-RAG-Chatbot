"""문서 DB가 반환한 지원 파일 경로만 RAG 입력으로 로드한다."""

from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from threading import RLock

from ingestion.loaders import load_markdown, load_pdf, load_text
from ingestion.types import RawDocument
from mcp_servers.document_tools.types import DocumentPathRecord

DOCUMENT_CACHE_MAX_ITEMS = 64
_document_cache: OrderedDict[tuple[str, str], RawDocument] = OrderedDict()
_cache_lock = RLock()


def load_document_files(records: list[DocumentPathRecord]) -> list[RawDocument]:
    """허용 경로와 DB 갱신 시각이 같은 문서는 파싱 결과를 안전하게 재사용한다."""
    documents: list[RawDocument] = []
    for record in records:
        path = Path(record["file_path"])
        cache_key = (str(path.resolve()), record["updated_at"])
        cached_document = _get_cached_document(cache_key)
        if cached_document is not None:
            documents.append(cached_document)
            continue
        suffix = path.suffix.casefold()
        if suffix == ".pdf":
            document = load_pdf(path)
        elif suffix in {".md", ".markdown"}:
            document = load_markdown(path)
        elif suffix == ".txt":
            document = load_text(path)
        else:
            continue
        document["document_id"] = record["document_id"]
        document["title"] = record["title"]
        document["metadata"]["updated_at"] = record["updated_at"]
        _put_cached_document(cache_key, document)
        documents.append(deepcopy(document))
    return documents


def invalidate_document_cache() -> None:
    """문서 등록·교체 작업 뒤 프로세스 내 파싱 캐시를 명시적으로 비운다."""
    with _cache_lock:
        _document_cache.clear()


def _get_cached_document(cache_key: tuple[str, str]) -> RawDocument | None:
    """호출자가 캐시 객체를 변경하지 못하도록 방어적 사본을 반환한다."""
    with _cache_lock:
        document = _document_cache.get(cache_key)
        if document is None:
            return None
        _document_cache.move_to_end(cache_key)
        return deepcopy(document)


def _put_cached_document(cache_key: tuple[str, str], document: RawDocument) -> None:
    """오래 사용하지 않은 항목부터 제거하는 제한된 LRU 캐시에 저장한다."""
    with _cache_lock:
        _document_cache[cache_key] = deepcopy(document)
        _document_cache.move_to_end(cache_key)
        while len(_document_cache) > DOCUMENT_CACHE_MAX_ITEMS:
            _document_cache.popitem(last=False)
