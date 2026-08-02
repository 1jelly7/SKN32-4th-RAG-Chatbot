"""
문서 DB의 전체 경로로 새 FAISS 인덱스 버전을 빌드하고, 정합성 검사를 통과한
경우에만 활성 인덱스를 교체합니다. 검사에 실패하면 기존 인덱스를 그대로 둡니다.

실행:
    python scripts/rebuild_faiss_index.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from ingestion.chunking import chunk_document
from ingestion.embedding import embed
from ingestion.index import build_index
from ingestion.loaders import load_pdf, load_markdown, load_text
from ingestion.metadata import build_metadata
from mcp_servers.document_tools.document_db import DocumentPathRepository
from mcp_servers.document_tools.faiss_store import FaissStore

CHUNK_SIZE = 500
CHUNK_OVERLAP = 80


def _load_by_extension(path: Path):
    suffix = path.suffix.casefold()
    if suffix == ".pdf":
        return load_pdf(path)
    if suffix in {".md", ".markdown"}:
        return load_markdown(path)
    if suffix == ".txt":
        return load_text(path)
    return None


async def main() -> None:
    """후보 인덱스를 검증한 뒤에만 활성 FAISS 파일을 교체한다."""
    # 이 CLI는 내부 문서 DB에서 전체 파일 경로를 조회하고 해당 파일들로 새 버전을 빌드한다.
    # 새 인덱스와 metadata의 정합성을 검사한 후에만 활성 경로를 교체하고, 실패 시 기존
    # 검색 가능한 버전을 보존한다. 결과 버전은 캐시 무효화/키 계산에 사용될 수 있어야 한다.
    settings = get_settings()

    repository = DocumentPathRepository(
        host=settings.document_db_host,
        user=settings.document_db_user,
        password=settings.document_db_password,
        database=settings.document_db_database,
    )
    repository.ensure_schema()

    records = await repository.find_paths("")
    if not records:
        print("문서 DB에 등록된 문서가 없습니다. 재인덱싱을 건너뜁니다.")
        return

    all_chunks = []
    for record in records:
        path = Path(record["file_path"])
        document = _load_by_extension(path)
        if document is None:
            continue
        document["document_id"] = record["document_id"]
        document["title"] = record["title"]
        metadata = build_metadata(document)
        document["metadata"].update(metadata)
        all_chunks.extend(chunk_document(document, CHUNK_SIZE, CHUNK_OVERLAP))

    if not all_chunks:
        print("인덱싱할 chunk가 없어 재인덱싱을 중단합니다. 기존 인덱스를 유지합니다.")
        return

    vectors = embed([chunk["content"] for chunk in all_chunks])

    active_path = Path(settings.faiss_path)
    staging_path = Path(tempfile.mkdtemp(prefix="faiss_rebuild_"))

    try:
        result = build_index(all_chunks, vectors, staging_path)

        # 새로 만든 인덱스를 실제로 로드해봐서 정합성(벡터 수/차원/버전)을 검증합니다.
        # 여기서 예외가 나면 아래 except에서 잡아 기존 활성 인덱스를 건드리지 않습니다.
        FaissStore(staging_path / "index.faiss").load()

        # 검증을 통과한 경우에만 활성 경로를 교체합니다.
        active_path.mkdir(parents=True, exist_ok=True)
        for filename in ("index.faiss", "metadata.json"):
            shutil.move(str(staging_path / filename), str(active_path / filename))

        print(f"재인덱싱 완료: index_version={result['index_version']}, chunk_count={result['chunk_count']}")
        print("이 index_version을 캐시 무효화 트리거에 사용할 수 있습니다.")

    except Exception as exc:  # noqa: BLE001
        print(f"재인덱싱 실패, 기존 인덱스를 유지합니다: {exc}")
        raise
    finally:
        shutil.rmtree(staging_path, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
