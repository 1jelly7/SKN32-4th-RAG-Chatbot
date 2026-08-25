# -*- coding: utf-8 -*-
"""DocumentService + EmbeddingService + FaissVectorStore + RagService를
실제 객체로 조합해 전체 파이프라인을 검증합니다. (API 키 불필요)
"""

import pytest

from app.config.settings import Settings
from app.services.document_service import DocumentService
from app.services.prompt_service import PromptService
from app.services.rag_service import RagService
from app.llm.embedding_service import EmbeddingService
from app.llm.openai_service import OpenAIService
from app.vectordb.faiss_store import FaissVectorStore


@pytest.fixture
def rag_service(tmp_path):
    settings = Settings(
        docs_dir=tmp_path / "docs",
        faiss_dir=tmp_path / "faiss",
        embedding_backend="local",
        openai_api_key="",
        local_embedding_dimension=128,
        chunk_size=200,
        chunk_overlap=20,
    )
    settings.docs_dir.mkdir(parents=True, exist_ok=True)
    (settings.docs_dir / "법인카드.txt").write_text(
        "법인카드 사용 기준: 법인카드는 회사 업무 목적에 한하여 사용할 수 있다. "
        "사용 후에는 반드시 영수증을 제출해야 한다.",
        encoding="utf-8",
    )
    (settings.docs_dir / "휴가규정.txt").write_text(
        "연차 유급휴가는 입사 1년 이상 근무한 직원에게 매년 15일이 부여된다.",
        encoding="utf-8",
    )

    document_service = DocumentService(settings)
    embedding_service = EmbeddingService(settings)
    vector_store = FaissVectorStore(settings.faiss_dir, embedding_service.dimension)
    openai_service = OpenAIService(settings)
    prompt_service = PromptService()

    service = RagService(
        document_service=document_service,
        embedding_service=embedding_service,
        vector_store=vector_store,
        openai_service=openai_service,
        prompt_service=prompt_service,
    )
    service.rebuild_index()
    return service


def test_rebuild_index_returns_chunk_count(rag_service):
    result = rag_service.rebuild_index()
    assert result["indexed_chunks"] >= 2


def test_search_returns_relevant_source(rag_service):
    results = rag_service.search("법인카드 사용 기준이 뭐야", top_k=2)
    assert len(results) > 0
    assert results[0]["source"] == "법인카드.txt"


def test_ask_without_api_key_returns_demo_answer_with_matches(rag_service):
    """API 키가 없어도 검색은 되고, 데모 응답에 검색 문맥이 포함되어야 합니다."""
    result = rag_service.ask("연차는 며칠 주어지나요", top_k=2)
    assert "로컬 RAG 데모 응답" in result["answer"]
    assert "휴가규정.txt" in result["sources"]
    assert len(result["matches"]) > 0


def test_ask_with_no_matching_documents_returns_guidance_message(tmp_path):
    """문서가 하나도 없을 때는 재구축을 안내하는 메시지를 반환해야 합니다."""
    settings = Settings(
        docs_dir=tmp_path / "empty_docs",
        faiss_dir=tmp_path / "empty_faiss",
        embedding_backend="local",
        openai_api_key="",
    )
    settings.docs_dir.mkdir(parents=True, exist_ok=True)

    document_service = DocumentService(settings)
    embedding_service = EmbeddingService(settings)
    vector_store = FaissVectorStore(settings.faiss_dir, embedding_service.dimension)
    service = RagService(
        document_service=document_service,
        embedding_service=embedding_service,
        vector_store=vector_store,
        openai_service=OpenAIService(settings),
        prompt_service=PromptService(),
    )

    result = service.ask("아무 질문", top_k=3)
    assert result["sources"] == []
    assert "rebuild" in result["answer"]
