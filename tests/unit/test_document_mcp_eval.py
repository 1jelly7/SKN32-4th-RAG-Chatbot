"""tests/fixtures/cases/rag_cases.jsonl의 golden case로 RAG 검색 품질을 검증합니다.

이 테스트는 tests/fixtures/documents/의 소형 fixture 문서만 대상으로 하며,
실제 사내 규정 PDF나 MySQL 없이도 동작합니다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingestion.chunking import chunk_document
from ingestion.embedding import embed
from ingestion.loaders import load_documents
from mcp_servers.document_tools.faiss_store import FaissStore
from ingestion.index import build_index

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
CASES_PATH = FIXTURES_DIR / "cases" / "rag_cases.jsonl"
DOCUMENTS_DIR = FIXTURES_DIR / "documents"


def _load_cases() -> list[dict]:
    if not CASES_PATH.exists():
        return []
    lines = [line for line in CASES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


@pytest.fixture(scope="module")
def fixture_index(tmp_path_factory):
    documents = load_documents(DOCUMENTS_DIR)
    assert documents, "tests/fixtures/documents/에 fixture 문서가 없습니다."

    all_chunks = []
    for document in documents:
        all_chunks.extend(chunk_document(document, chunk_size=300, chunk_overlap=30))

    vectors = embed([c["content"] for c in all_chunks])
    output_path = tmp_path_factory.mktemp("fixture_faiss")
    build_index(all_chunks, vectors, output_path)

    store = FaissStore(output_path / "index.faiss")
    store.load()
    return store


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["question"])
def test_rag_case_finds_expected_document(fixture_index, case):
    query_vector = embed([case["question"]])[0]
    results = fixture_index.search(query_vector, top_k=1)

    assert results, f"'{case['question']}'에 대한 검색 결과가 없습니다."
    top_title = results[0]["title"]
    assert case["expected_document"] in top_title or top_title in case["expected_document"], (
        f"'{case['question']}' 질문에 예상 문서({case['expected_document']}) 대신 "
        f"'{top_title}'가 최상위로 나왔습니다."
    )
