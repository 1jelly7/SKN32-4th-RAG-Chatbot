from __future__ import annotations

from pathlib import Path

from mcp_servers.document.types import DocumentChunk, IndexMetadata


class FaissStore:
    def __init__(self, index_path: Path) -> None:
        ...

    def load(self) -> IndexMetadata:
        ...

    def search(self, vector: list[float], top_k: int) -> list[DocumentChunk]:
        ...
