"""
서비스 객체 생성과 의존성 조립을 한 곳에서 담당합니다.
"""

# 반복 호출 시 같은 Container를 재사용하기 위해 lru_cache를 가져옵니다.
from functools import lru_cache

# 프로젝트 설정을 가져옵니다.
from app.config.settings import get_settings

# 임베딩 서비스를 가져옵니다.
from app.llm.embedding_service import EmbeddingService

# OpenAI 서비스를 가져옵니다.
from app.llm.openai_service import OpenAIService

# 문서 서비스를 가져옵니다.
from app.services.document_service import DocumentService

# MySQL 서비스를 가져옵니다.
from app.services.mysql_service import MySQLService

# Prompt 서비스를 가져옵니다.
from app.services.prompt_service import PromptService

# RAG 서비스를 가져옵니다.
from app.services.rag_service import RagService

# FAISS 저장소를 가져옵니다.
from app.vectordb.faiss_store import FaissVectorStore

# Qdrant 저장소를 가져옵니다.
from app.vectordb.qdrant_store import QdrantVectorStore


# 애플리케이션에서 공유하는 서비스 묶음을 정의합니다.
class Container:
    """환경설정에 따라 필요한 구현을 생성하고 서로 연결합니다."""

    # 모든 서비스 객체를 생성합니다.
    def __init__(self) -> None:
        # 캐시된 설정 객체를 가져옵니다.
        self.settings = get_settings()

        # 문서 서비스를 생성합니다.
        self.document_service = DocumentService(self.settings)

        # 임베딩 서비스를 생성합니다.
        self.embedding_service = EmbeddingService(self.settings)

        # 설정에 따라 Qdrant 또는 FAISS 저장소를 생성합니다.
        if self.settings.vector_backend.lower() == "qdrant":
            self.vector_store = QdrantVectorStore(
                self.settings,
                self.embedding_service.dimension,
            )
        else:
            self.vector_store = FaissVectorStore(
                self.settings.faiss_dir,
                self.embedding_service.dimension,
            )

        # OpenAI 서비스를 생성합니다.
        self.openai_service = OpenAIService(self.settings)

        # Prompt 서비스를 생성합니다.
        self.prompt_service = PromptService()

        # MySQL 서비스를 생성합니다.
        self.mysql_service = MySQLService(self.settings)

        # 앞서 생성한 서비스를 연결하여 RAG 서비스를 생성합니다.
        self.rag_service = RagService(
            document_service=self.document_service,
            embedding_service=self.embedding_service,
            vector_store=self.vector_store,
            openai_service=self.openai_service,
            prompt_service=self.prompt_service,
        )


# Container를 한 번만 생성하여 재사용합니다.
@lru_cache
def get_container() -> Container:
    """애플리케이션 공용 Container를 반환합니다."""

    # 새 Container 객체를 생성하여 캐시에 저장하고 반환합니다.
    return Container()
