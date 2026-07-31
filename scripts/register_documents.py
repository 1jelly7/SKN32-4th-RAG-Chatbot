# -*- coding: utf-8 -*-
"""
data/raw/documents/ 폴더의 파일을 스캔해서, document_paths 테이블(erp_system DB)에
document_id / title / file_path / updated_at을 등록합니다.

실행:
    python scripts/register_documents.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from ingestion.loaders import load_documents
from ingestion.metadata import build_metadata
from mcp_servers.document_tools.document_db import DocumentPathRepository


def main() -> None:
    settings = get_settings()
    repository = DocumentPathRepository(
        host=settings.document_db_host,
        user=settings.document_db_user,
        password=settings.document_db_password,
        database=settings.document_db_database,
    )

    print("document_paths 테이블 준비 중...")
    repository.ensure_schema()

    documents_dir = PROJECT_ROOT / "data" / "raw" / "documents"
    documents = load_documents(documents_dir)

    if not documents:
        print(f"{documents_dir} 안에 등록할 파일이 없습니다.")
        return

    for document in documents:
        metadata = build_metadata(document)
        repository.upsert_path(
            document_id=metadata["document_id"],
            title=metadata["title"],
            file_path=document["path"],
            updated_at=metadata["updated_at"],
        )
        print(f"등록: {metadata['title']} (id={metadata['document_id']})")

    print(f"\n총 {len(documents)}건 등록 완료.")


if __name__ == "__main__":
    main()