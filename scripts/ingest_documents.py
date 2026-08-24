"""
문서 DB에 등록된 전체 경로를 조회해 배치로 문서를 인덱싱합니다.

실행:
    python scripts/ingest_documents.py
"""

from __future__ import annotations

import asyncio
import sys
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
    """문서 DB 등록 경로 전체를 읽어 새 FAISS 인덱스를 배치 생성한다."""
    # CLI는 API 요청 경로가 아니라 배치로만 문서 인덱싱을 실행해야 한다. 내부 문서 DB에서
    # 파일 경로를 조회한 뒤 load -> chunk/metadata -> embed -> build_index 순서로 호출하고,
    # 성공한 index_version·chunk_count만 요약 출력한다.
    # 부분 생성물은 원자적 index 교체가 끝나기 전 공개하지 않으며 원문/비밀값을 출력하지 않는다.
    settings = get_settings()

    repository = DocumentPathRepository(
        host=settings.document_db_host,
        user=settings.document_db_user,
        password=settings.document_db_password,
        database=settings.document_db_database,
    )
    repository.ensure_schema()

    records = await repository.find_paths("")  # 빈 질의는 활성 문서 전체를 반환합니다.
    if not records:
        print(
            "문서 DB에 등록된 문서가 없습니다. scripts/register_documents.py를 먼저 실행하세요."
        )
        return

    print(f"문서 DB에서 {len(records)}건의 경로를 조회했습니다.")

    all_chunks = []
    skipped = []
    for record in records:
        path = Path(record["file_path"])
        document = _load_by_extension(path)
        if document is None:
            skipped.append(record["title"])
            continue

        document["document_id"] = record["document_id"]
        document["title"] = record["title"]
        metadata = build_metadata(document)
        document["metadata"].update(metadata)

        all_chunks.extend(chunk_document(document, CHUNK_SIZE, CHUNK_OVERLAP))

    if skipped:
        print(f"지원하지 않는 형식이라 건너뛴 문서: {len(skipped)}건")

    if not all_chunks:
        print("인덱싱할 chunk가 없습니다.")
        return

    print(f"총 {len(all_chunks)}개 chunk 생성. 임베딩 계산 중...")
    vectors = embed([chunk["content"] for chunk in all_chunks])

    output_path = Path(settings.faiss_path)
    result = build_index(all_chunks, vectors, output_path)

    # 원문/비밀값 없이 요약 정보만 출력합니다.
    print(
        f"인덱싱 완료: index_version={result['index_version']}, chunk_count={result['chunk_count']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
