"""
문서 인덱싱, Vector Search, RAG 답변 생성을 통합합니다.
"""

# 미래 타입 힌트 평가 방식을 사용합니다.
from __future__ import annotations

# 임베딩 서비스를 가져옵니다.
from app.llm.embedding_service import EmbeddingService

# OpenAI 답변 생성 서비스를 가져옵니다.
from app.llm.openai_service import OpenAIService

# 문서 서비스를 가져옵니다.
from app.services.document_service import DocumentService

# Prompt 서비스를 가져옵니다.
from app.services.prompt_service import PromptService

# 벡터 저장소 공통 인터페이스를 가져옵니다.
from app.vectordb.base import VectorStore


# RAG 서비스 클래스를 정의합니다.
class RagService:
    """문서 적재, 검색, 답변 생성을 한 곳에서 처리합니다."""

    # 필요한 하위 서비스를 생성자에서 전달받습니다.
    def __init__(
        self,
        document_service: DocumentService,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        openai_service: OpenAIService,
        prompt_service: PromptService,
    ) -> None:
        # 문서 서비스를 저장합니다.
        self.document_service = document_service

        # 임베딩 서비스를 저장합니다.
        self.embedding_service = embedding_service

        # 벡터 저장소를 저장합니다.
        self.vector_store = vector_store

        # OpenAI 서비스를 저장합니다.
        self.openai_service = openai_service

        # Prompt 서비스를 저장합니다.
        self.prompt_service = prompt_service

    # docs 폴더 전체를 다시 인덱싱합니다.
    def rebuild_index(self) -> dict:
        """전체 문서를 청크로 분할하고 벡터 저장소를 재구축합니다."""

        # docs 폴더에서 검색용 청크를 읽습니다.
        documents = self.document_service.load_chunks()

        # 각 청크의 본문만 추출합니다.
        texts = [document["content"] for document in documents]

        # 전체 문서 청크를 임베딩 벡터로 변환합니다.
        vectors = self.embedding_service.embed_documents(texts) if texts else []

        # 선택한 벡터 저장소를 전체 재구축합니다.
        count = self.vector_store.rebuild(documents, vectors)

        # 처리 결과를 API 응답용 딕셔너리로 반환합니다.
        return {"indexed_chunks": count}

    # 질문과 유사한 문서를 검색합니다.
    def search(self, query: str, top_k: int) -> list[dict]:
        """Vector Search 결과를 반환합니다."""

        # 질문을 임베딩 벡터로 변환합니다.
        query_vector = self.embedding_service.embed_query(query)

        # 벡터 저장소에서 유사 문서를 검색합니다.
        return self.vector_store.search(query_vector, top_k)

    # RAG 답변과 출처를 생성합니다.
    def ask(self, question: str, top_k: int) -> dict:
        """검색 문맥을 근거로 답변을 생성합니다."""

        # 질문과 유사한 문서를 검색합니다.
        results = self.search(question, top_k)

        # 검색 결과가 없으면 먼저 인덱스를 만들라는 메시지를 반환합니다.
        if not results:
            return {
                "answer": "검색 결과가 없습니다. 먼저 /api/rag/rebuild를 실행하세요.",
                "sources": [],
                "matches": [],
            }

        # 각 검색 결과를 출처와 본문이 포함된 문맥 문자열로 변환합니다.
        context = "\n\n".join(
            f"[출처: {item.get('source', 'unknown')}]\n{item.get('content', '')}"
            for item in results
        )

        # RAG Prompt 템플릿을 조회합니다.
        prompt_template = self.prompt_service.get_prompt("rag_answer")

        # OpenAI 또는 로컬 대체 방식으로 답변을 생성합니다.
        answer = self.openai_service.answer_with_context(
            question=question,
            context=context,
            prompt_template=prompt_template,
        )

        # 중복되지 않은 출처 파일명을 순서대로 구성합니다.
        sources = list(dict.fromkeys(item.get("source", "unknown") for item in results))

        # 답변, 출처, 검색 상세 결과를 반환합니다.
        return {"answer": answer, "sources": sources, "matches": results}
