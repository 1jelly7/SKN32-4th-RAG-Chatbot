"""
Qdrant local 또는 server 모드 벡터 저장소를 구현합니다.
"""

# UUID 형태의 고유 문서 ID를 만들기 위해 uuid4를 가져옵니다.
from uuid import uuid4

# Qdrant 클라이언트를 가져옵니다.
from qdrant_client import QdrantClient

# Qdrant 컬렉션과 Point 구조를 정의하는 모델을 가져옵니다.
from qdrant_client.models import Distance, PointStruct, VectorParams

# 설정 모델을 가져옵니다.
from app.config.settings import Settings

# 공통 벡터 저장소 인터페이스를 가져옵니다.
from app.vectordb.base import SearchResult, VectorStore


# Qdrant 저장소 클래스를 정의합니다.
class QdrantVectorStore(VectorStore):
    """Qdrant에 문서 벡터와 payload를 저장합니다."""

    # 설정과 벡터 차원을 전달받습니다.
    def __init__(self, settings: Settings, dimension: int) -> None:
        # 설정을 저장합니다.
        self.settings = settings

        # 벡터 차원을 저장합니다.
        self.dimension = dimension

        # 사용할 컬렉션 이름을 저장합니다.
        self.collection_name = settings.qdrant_collection

        # local 모드이면 프로젝트 내부 디렉터리를 사용하는 클라이언트를 생성합니다.
        if settings.qdrant_mode.lower() == "local":
            self.client = QdrantClient(path=str(settings.qdrant_dir))
        else:
            # server 모드이면 외부 Qdrant 서버 주소를 사용합니다.
            self.client = QdrantClient(url=settings.qdrant_url)

    # 컬렉션 전체를 새로 구성합니다.
    def rebuild(self, documents: list[dict], vectors: list[list[float]]) -> int:
        """기존 컬렉션을 교체하고 문서를 저장합니다."""

        # 기존 컬렉션이 존재하면 삭제합니다.
        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)

        # 코사인 거리와 임베딩 차원을 사용하여 컬렉션을 생성합니다.
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
        )

        # 문서와 벡터를 Qdrant Point 목록으로 변환합니다.
        points = [
            PointStruct(id=str(uuid4()), vector=vector, payload=document)
            for document, vector in zip(documents, vectors)
        ]

        # Point가 있을 때만 Qdrant에 저장합니다.
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)

        # 저장한 문서 수를 반환합니다.
        return len(points)

    # 유사 문서를 검색합니다.
    def search(self, query_vector: list[float], top_k: int) -> list[SearchResult]:
        """Qdrant에서 유사 문서를 검색합니다."""

        # 컬렉션이 없으면 빈 결과를 반환합니다.
        if not self.client.collection_exists(self.collection_name):
            return []

        # 최신 query_points API로 유사 벡터를 검색합니다.
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )

        # 최종 결과 목록을 생성합니다.
        results: list[SearchResult] = []

        # 검색된 Point를 순회합니다.
        for point in response.points:
            # payload가 없을 수 있으므로 빈 딕셔너리를 기본값으로 복사합니다.
            item = dict(point.payload or {})

            # Qdrant 유사도 점수를 추가합니다.
            item["score"] = float(point.score)

            # 완성한 결과를 목록에 추가합니다.
            results.append(item)

        # 검색 결과를 반환합니다.
        return results
