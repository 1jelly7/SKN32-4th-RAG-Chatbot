"""ingestion/ 모듈(loaders, chunking, embedding, index, metadata)을 검증합니다."""

from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.chunking import chunk_document
from ingestion.embedding import EmbeddingClient
from ingestion.index import build_index, get_index_version
from ingestion.loaders import load_documents, load_markdown, load_pdf, load_text
from ingestion.metadata import build_metadata


# ------------------------------------------------------------------
# loaders.py
# ------------------------------------------------------------------
def test_load_text_reads_utf8_content(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("안녕하세요 반갑습니다", encoding="utf-8")

    document = load_text(path)

    assert document["content"] == "안녕하세요 반갑습니다"
    assert document["title"] == "sample"
    assert document["metadata"]["source_type"] == "text"


def test_load_markdown_extracts_first_header_as_title(tmp_path):
    path = tmp_path / "guide.md"
    path.write_text("# 사용 가이드\n\n내용입니다.", encoding="utf-8")

    document = load_markdown(path)

    assert document["title"] == "사용 가이드"
    assert "사용 가이드" in document["metadata"]["headers"]


def test_load_pdf_preserves_page_boundaries_with_form_feed(tmp_path):
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    pdf_path = tmp_path / "sample.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(100, 750, "Page One Content")
    c.showPage()
    c.drawString(100, 750, "Page Two Content")
    c.save()

    document = load_pdf(pdf_path)

    assert document["metadata"]["page_count"] == 2
    assert "\f" in document["content"]
    pages = document["content"].split("\f")
    assert len(pages) == 2


def test_load_documents_skips_unsupported_extensions(tmp_path):
    (tmp_path / "a.txt").write_text("텍스트", encoding="utf-8")
    (tmp_path / "b.exe").write_bytes(b"binary")

    documents = load_documents(tmp_path)

    assert len(documents) == 1
    assert documents[0]["title"] == "a"


def test_load_documents_same_path_always_same_document_id(tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("내용", encoding="utf-8")

    first = load_text(path)
    second = load_text(path)

    assert first["document_id"] == second["document_id"]


# ------------------------------------------------------------------
# chunking.py
# ------------------------------------------------------------------
def _make_raw_document(content: str) -> dict:
    return {
        "document_id": "doc-1",
        "path": "/fake/path.txt",
        "title": "테스트 문서",
        "content": content,
        "metadata": {},
    }


def test_chunk_document_respects_chunk_size():
    document = _make_raw_document("가" * 1000)
    chunks = chunk_document(document, chunk_size=200, chunk_overlap=20)

    assert len(chunks) > 1
    assert all(len(c["content"]) <= 200 for c in chunks)


def test_chunk_document_rejects_invalid_size_overlap_combo():
    document = _make_raw_document("내용")
    with pytest.raises(ValueError):
        chunk_document(document, chunk_size=100, chunk_overlap=100)
    with pytest.raises(ValueError):
        chunk_document(document, chunk_size=0, chunk_overlap=0)


def test_chunk_document_tracks_page_number_from_form_feed():
    document = _make_raw_document("첫 페이지 내용\f두번째 페이지 내용")
    chunks = chunk_document(document, chunk_size=100, chunk_overlap=10)

    pages = {c["metadata"]["page"] for c in chunks}
    assert pages == {1, 2}


def test_chunk_document_copies_document_id_to_every_chunk():
    document = _make_raw_document("문단 하나\n\n문단 둘\n\n문단 셋")
    chunks = chunk_document(document, chunk_size=50, chunk_overlap=5)

    assert all(c["document_id"] == "doc-1" for c in chunks)
    assert all(c["metadata"]["document_id"] == "doc-1" for c in chunks)


def test_chunk_document_removes_empty_pieces():
    document = _make_raw_document("내용\n\n\n\n\n\n더 내용")
    chunks = chunk_document(document, chunk_size=50, chunk_overlap=5)

    assert all(c["content"].strip() for c in chunks)


# ------------------------------------------------------------------
# embedding.py
# ------------------------------------------------------------------
def test_embedding_client_returns_consistent_dimension():
    client = EmbeddingClient(dimension=128)
    vectors = client.embed(["첫번째 문장", "두번째 문장"])

    assert len(vectors) == 2
    assert all(len(v) == 128 for v in vectors)


def test_embedding_client_is_deterministic():
    client = EmbeddingClient(dimension=64)
    v1 = client.embed(["같은 문장"])[0]
    v2 = client.embed(["같은 문장"])[0]
    assert v1 == v2


def test_embedding_client_rejects_empty_text():
    client = EmbeddingClient(dimension=64)
    with pytest.raises(ValueError):
        client.embed(["정상 문장", ""])


def test_embedding_client_similar_words_score_higher_than_unrelated():
    client = EmbeddingClient(dimension=256)
    a = client.embed(["법인카드는 어떻게 사용하나요"])[0]
    b = client.embed(["법인카드를 사용하는 기준"])[0]
    c = client.embed(["오늘 점심 메뉴 추천해줘"])[0]

    cos_ab = sum(x * y for x, y in zip(a, b))
    cos_ac = sum(x * y for x, y in zip(a, c))
    assert cos_ab > cos_ac


# ------------------------------------------------------------------
# index.py
# ------------------------------------------------------------------
def _make_chunks_and_vectors(n: int, dimension: int = 32):
    chunks = [
        {
            "chunk_id": f"c{i}",
            "document_id": "doc-1",
            "content": f"내용 {i}",
            "metadata": {"title": "t", "updated_at": "now"},
        }
        for i in range(n)
    ]
    vectors = [[0.1 * (j + 1) for j in range(dimension)] for _ in range(n)]
    return chunks, vectors


def test_build_index_creates_index_and_metadata_files(tmp_path):
    chunks, vectors = _make_chunks_and_vectors(5)
    result = build_index(chunks, vectors, tmp_path)

    assert Path(result["index_path"]).exists()
    assert Path(result["metadata_path"]).exists()
    assert result["chunk_count"] == 5


def test_build_index_rejects_mismatched_chunk_and_vector_counts(tmp_path):
    chunks, vectors = _make_chunks_and_vectors(5)
    with pytest.raises(ValueError):
        build_index(chunks, vectors[:3], tmp_path)


def test_build_index_rejects_inconsistent_vector_dimensions(tmp_path):
    chunks, vectors = _make_chunks_and_vectors(3, dimension=16)
    vectors[1] = vectors[1][:8]  # 차원을 일부러 다르게 만듦
    with pytest.raises(ValueError):
        build_index(chunks, vectors, tmp_path)


def test_get_index_version_reads_version_after_build(tmp_path):
    chunks, vectors = _make_chunks_and_vectors(3)
    result = build_index(chunks, vectors, tmp_path)

    version = get_index_version(Path(result["index_path"]))
    assert version == result["index_version"]


def test_get_index_version_fails_clearly_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        get_index_version(tmp_path / "index.faiss")


def test_build_index_each_call_produces_new_version(tmp_path):
    chunks, vectors = _make_chunks_and_vectors(3)
    result1 = build_index(chunks, vectors, tmp_path)
    result2 = build_index(chunks, vectors, tmp_path)
    assert result1["index_version"] != result2["index_version"]


# ------------------------------------------------------------------
# metadata.py
# ------------------------------------------------------------------
def test_build_metadata_uses_file_mtime(tmp_path):
    path = tmp_path / "doc.txt"
    path.write_text("내용", encoding="utf-8")
    document = {
        "document_id": "doc-1",
        "path": str(path),
        "title": "제목",
        "content": "내용",
        "metadata": {},
    }

    metadata = build_metadata(document)

    assert metadata["title"] == "제목"
    assert "updated_at" in metadata


def test_build_metadata_falls_back_to_filename_when_no_title(tmp_path):
    path = tmp_path / "이름없는문서.txt"
    path.write_text("내용", encoding="utf-8")
    document = {
        "document_id": "doc-1",
        "path": str(path),
        "title": "",
        "content": "내용",
        "metadata": {},
    }

    metadata = build_metadata(document)
    assert metadata["title"] == "이름없는문서"
