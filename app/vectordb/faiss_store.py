"""
FAISS 기반 로컬 벡터 저장소를 구현합니다.
"""

# JSON 메타데이터를 저장하고 읽기 위해 json을 가져옵니다.
import json

# 파일 경로를 처리하기 위해 Path를 가져옵니다.
from pathlib import Path

# FAISS 인덱스를 생성하고 검색하기 위해 faiss를 가져옵니다.
import faiss

# 벡터 배열 계산을 위해 NumPy를 가져옵니다.
import numpy as np

# 공통 벡터 저장소 인터페이스를 가져옵니다.
from app.vectordb.base import SearchResult, VectorStore


# FAISS 저장소 클래스를 정의합니다.
class FaissVectorStore(VectorStore):
    """FAISS 인덱스와 JSON 메타데이터를 디스크에 저장합니다."""

    # 저장 디렉터리와 임베딩 차원을 전달받습니다.
    def __init__(self, directory: Path, dimension: int) -> None:
        # 저장 디렉터리를 저장합니다.
        self.directory = directory

        # 임베딩 차원을 저장합니다.
        self.dimension = dimension

        # 저장 디렉터리가 없으면 생성합니다.
        self.directory.mkdir(parents=True, exist_ok=True)

        # FAISS 인덱스 파일 경로를 정의합니다.
        self.index_path = self.directory / "documents.faiss"

        # 문서 메타데이터 JSON 파일 경로를 정의합니다.
        self.meta_path = self.directory / "documents.json"

    # 인덱스를 전체 재구축합니다.
    def rebuild(self, documents: list[dict], vectors: list[list[float]]) -> int:
        """문서와 벡터를 이용해 FAISS 인덱스를 새로 만듭니다."""

        # 벡터가 없으면 빈 인덱스를 생성합니다.
        matrix = np.asarray(vectors, dtype=np.float32)

        # 코사인 유사도 검색을 위해 각 벡터를 L2 정규화합니다.
        if len(matrix) > 0:
            faiss.normalize_L2(matrix)

        # 내적 기반의 단순하고 정확한 Flat 인덱스를 생성합니다.
        index = faiss.IndexFlatIP(self.dimension)

        # 벡터가 존재하는 경우에만 인덱스에 추가합니다.
        if len(matrix) > 0:
            index.add(matrix)

        # 완성된 FAISS 인덱스를 파일로 저장합니다.
        faiss.write_index(index, str(self.index_path))

        # 문서 내용과 출처 메타데이터를 JSON 파일로 저장합니다.
        self.meta_path.write_text(
            json.dumps(documents, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 저장한 문서 수를 반환합니다.
        return len(documents)

    # 질문 벡터와 유사한 문서를 검색합니다.
    def search(self, query_vector: list[float], top_k: int) -> list[SearchResult]:
        """FAISS 인덱스에서 유사 문서를 검색합니다."""

        # 인덱스 또는 메타데이터 파일이 없으면 빈 결과를 반환합니다.
        if not self.index_path.exists() or not self.meta_path.exists():
            return []

        # 디스크에서 FAISS 인덱스를 읽습니다.
        index = faiss.read_index(str(self.index_path))

        # 디스크에서 문서 메타데이터 목록을 읽습니다.
        documents = json.loads(self.meta_path.read_text(encoding="utf-8"))

        # 질문 벡터를 2차원 float32 배열로 변환합니다.
        query = np.asarray([query_vector], dtype=np.float32)

        # 코사인 유사도에 맞게 질문 벡터를 정규화합니다.
        faiss.normalize_L2(query)

        # 저장된 문서 수를 넘지 않도록 실제 검색 개수를 결정합니다.
        limit = min(top_k, index.ntotal)

        # 인덱스가 비어 있으면 빈 목록을 반환합니다.
        if limit == 0:
            return []

        # FAISS에서 점수와 문서 위치를 검색합니다.
        scores, indices = index.search(query, limit)

        # 최종 검색 결과를 저장할 목록을 생성합니다.
        results: list[SearchResult] = []

        # 검색된 인덱스와 점수를 함께 순회합니다.
        for position, score in zip(indices[0], scores[0]):
            # 유효하지 않은 인덱스는 건너뜁니다.
            if position < 0:
                continue

            # 원본 문서 메타데이터를 복사합니다.
            item = dict(documents[position])

            # 검색 점수를 float 값으로 추가합니다.
            item["score"] = float(score)

            # 완성한 항목을 결과 목록에 추가합니다.
            results.append(item)

        # 유사도 순으로 정렬된 결과를 반환합니다.
        return results
