"""
벡터 저장소가 공통으로 구현해야 할 인터페이스를 정의합니다.
"""

# 추상 클래스를 정의하기 위해 ABC와 abstractmethod를 가져옵니다.
from abc import ABC, abstractmethod

# 임의 형태의 메타데이터 타입을 표현하기 위해 Any를 가져옵니다.
from typing import Any


# 벡터 검색 결과 자료형을 정의합니다.
SearchResult = dict[str, Any]


# 벡터 저장소 공통 인터페이스를 정의합니다.
class VectorStore(ABC):
    """FAISS와 Qdrant가 동일한 방식으로 호출되도록 하는 추상 클래스입니다."""

    # 문서와 벡터를 저장하는 메서드를 추상 메서드로 정의합니다.
    @abstractmethod
    def rebuild(self, documents: list[dict], vectors: list[list[float]]) -> int:
        """기존 인덱스를 교체하고 전체 문서를 새로 저장합니다."""

    # 질문 벡터와 유사한 문서를 검색하는 메서드를 추상 메서드로 정의합니다.
    @abstractmethod
    def search(self, query_vector: list[float], top_k: int) -> list[SearchResult]:
        """질문 벡터와 가까운 문서를 반환합니다."""
