# -*- coding: utf-8 -*-
"""DocumentService의 파일 로딩과 청킹 로직을 검증합니다."""

import pytest

from app.config.settings import Settings
from app.services.document_service import DocumentService


@pytest.fixture
def settings(tmp_path):
    """임시 docs 폴더를 사용하는 테스트용 Settings를 만듭니다."""
    return Settings(
        docs_dir=tmp_path / "docs",
        chunk_size=20,
        chunk_overlap=5,
    )


def test_list_files_only_returns_supported_extensions(settings):
    settings.docs_dir.mkdir(parents=True, exist_ok=True)
    (settings.docs_dir / "a.txt").write_text("hello", encoding="utf-8")
    (settings.docs_dir / "b.md").write_text("hello", encoding="utf-8")
    (settings.docs_dir / "c.unsupported").write_text("hello", encoding="utf-8")

    service = DocumentService(settings)
    files = service.list_files()

    assert "a.txt" in files
    assert "b.md" in files
    assert "c.unsupported" not in files


def test_split_text_respects_chunk_size_and_overlap(settings):
    service = DocumentService(settings)
    text = "가" * 50  # chunk_size=20, overlap=5 → step=15

    chunks = service._split_text(text)

    assert all(len(c) <= settings.chunk_size for c in chunks)
    # 마지막 청크까지 전체 텍스트를 빠짐없이 커버해야 합니다.
    assert "".join(chunks)[: settings.chunk_size] == text[: settings.chunk_size]


def test_split_text_empty_input_returns_empty_list(settings):
    service = DocumentService(settings)
    assert service._split_text("   ") == []


def test_load_chunks_attaches_source_and_index_metadata(settings):
    settings.docs_dir.mkdir(parents=True, exist_ok=True)
    (settings.docs_dir / "doc1.txt").write_text("가" * 50, encoding="utf-8")

    service = DocumentService(settings)
    chunks = service.load_chunks()

    assert len(chunks) > 0
    assert all(c["source"] == "doc1.txt" for c in chunks)
    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_load_chunks_reads_pdf_text(settings, tmp_path):
    """실제 PDF 파일을 만들어 텍스트 추출이 되는지 확인합니다."""
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    settings.docs_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = settings.docs_dir / "sample.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(100, 750, "Hello RAG Test")
    c.save()

    service = DocumentService(settings)
    chunks = service.load_chunks()

    assert any("sample.pdf" == c["source"] for c in chunks)
    assert any("Hello" in c["content"] for c in chunks)
