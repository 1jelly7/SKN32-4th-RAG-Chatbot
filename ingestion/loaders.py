from pathlib import Path

from ingestion.types import RawDocument


def load_documents(path: Path) -> list[RawDocument]:
    ...


def load_pdf(path: Path) -> RawDocument:
    ...


def load_text(path: Path) -> RawDocument:
    ...


def load_markdown(path: Path) -> RawDocument:
    ...
