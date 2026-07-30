from pathlib import Path

from ingestion.types import DocumentChunk, IndexBuildResult


def build_index(
    chunks: list[DocumentChunk],
    vectors: list[list[float]],
    output_path: Path,
) -> IndexBuildResult:
    ...


def get_index_version(index_path: Path) -> str:
    ...
