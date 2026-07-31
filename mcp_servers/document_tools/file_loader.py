from pathlib import Path

from ingestion.loaders import load_markdown, load_pdf, load_text
from ingestion.types import RawDocument
from mcp_servers.document_tools.types import DocumentPathRecord


def load_document_files(records: list[DocumentPathRecord]) -> list[RawDocument]:
    """문서 DB가 반환한 경로의 지원 파일만 읽어 RAG 입력 문서로 변환한다."""
    documents: list[RawDocument] = []
    for record in records:
        path = Path(record["file_path"])
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
        documents.append(document)
    return documents
