from typing import Any

from ingestion.types import DocumentChunk, RawDocument


def build_metadata(document: RawDocument) -> dict[str, Any]:
    ...


def apply_acl(chunk: DocumentChunk, allowed_roles: list[str]) -> DocumentChunk:
    ...
