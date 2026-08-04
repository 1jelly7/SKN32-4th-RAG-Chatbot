"""FAISS 인덱스와 동일 순서의 chunk metadata를 검증·검색한다."""

from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

from mcp_servers.document_tools.types import DocumentChunk, IndexMetadata

METADATA_FILENAME = "metadata.json"
GENERIC_SEARCH_TERMS = {
    "관련",
    "규정",
    "내용",
    "대상",
    "방법",
    "사항",
    "절차",
    "정책",
    "지침",
}


class FaissStore:
    """FAISS 인덱스와 chunk metadata를 함께 다루는 읽기 전용 저장소."""

    def __init__(self, index_path: Path) -> None:
        """인덱스 경로와 대응 metadata 경로를 보관하되 즉시 대용량 파일을 읽지 않는다."""
        self._index_path = index_path
        self._metadata_path = index_path.parent / METADATA_FILENAME
        self._index: faiss.Index | None = None
        self._chunks: list[dict] = []
        self._dimension: int | None = None

    def load(self) -> IndexMetadata:
        """FAISS 파일과 metadata 파일의 존재·버전·개수·차원을 검증해 메모리에 로드한다.

        둘 중 하나만 갱신된 불일치나 손상은 검색 결과로 숨기지 말고 안전하게 실패시킵니다.
        """
        if not self._index_path.exists():
            raise FileNotFoundError(f"FAISS 인덱스가 없습니다: {self._index_path} (재인덱싱이 필요합니다)")
        if not self._metadata_path.exists():
            raise FileNotFoundError(f"인덱스 metadata가 없습니다: {self._metadata_path}")

        try:
            payload = json.loads(self._metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"인덱스 metadata가 손상되었습니다: {self._metadata_path}") from exc

        index = faiss.read_index(str(self._index_path))

        chunks = payload.get("chunks", [])
        chunk_count = payload.get("chunk_count")
        dimension = payload.get("dimension")

        # FAISS 인덱스에 실제로 들어있는 벡터 수와 metadata의 chunk 수가 반드시 같아야 합니다.
        if index.ntotal != len(chunks):
            raise ValueError(
                f"인덱스 벡터 수({index.ntotal})와 metadata chunk 수({len(chunks)})가 일치하지 않습니다. "
                "재인덱싱이 필요합니다."
            )
        if chunk_count is not None and chunk_count != len(chunks):
            raise ValueError("metadata의 chunk_count와 실제 chunk 목록 길이가 일치하지 않습니다.")
        if dimension is not None and dimension != index.d:
            raise ValueError(f"metadata 차원({dimension})과 FAISS 인덱스 차원({index.d})이 일치하지 않습니다.")

        self._index = index
        self._chunks = chunks
        self._dimension = index.d

        return {
            "index_version": payload["index_version"],
            "created_at": payload["created_at"],
            "chunk_count": len(chunks),
        }

    def search(self, vector: list[float], top_k: int) -> list[DocumentChunk]:
        """로드된 인덱스에서 top_k 후보를 거리/점수와 함께 반환한다.

        query vector 차원과 top_k 상한을 검증하고, 검색 결과의 index id를 metadata와
        정확히 매핑합니다. 내부 file_path는 검색 처리에만 쓰고 반환 청크에서는 뺍니다.
        """
        if self._index is None:
            raise RuntimeError("FaissStore.load()를 먼저 호출해야 합니다.")

        if len(vector) != self._dimension:
            raise ValueError(f"query vector 차원({len(vector)})이 인덱스 차원({self._dimension})과 다릅니다.")

        if top_k <= 0:
            raise ValueError("top_k는 1 이상이어야 합니다.")
        # 인덱스에 있는 것보다 많이 요청하면 있는 만큼만 반환합니다.
        effective_k = min(top_k, self._index.ntotal)

        query_matrix = np.array([vector], dtype=np.float32)
        faiss.normalize_L2(query_matrix)

        scores, indices = self._index.search(query_matrix, effective_k)

        results: list[DocumentChunk] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS가 후보 부족 시 -1을 채워 넣는 경우 방지
                continue
            chunk = self._chunks[idx]
            metadata = chunk.get("metadata", {})
            results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "document_id": chunk["document_id"],
                    "title": metadata.get("title", ""),
                    "content": chunk["content"],
                    "score": float(score),
                    "updated_at": metadata.get("updated_at", ""),
                    "page": metadata.get("page"),
                }
            )
        return results

    def search_text(self, query: str, top_k: int) -> list[DocumentChunk]:
        """의미 벡터가 놓친 명시적 업무 용어를 정확 일치 후보로 보완한다.

        로컬 n-gram 임베딩은 짧은 한국어 업무 용어에서 해시 충돌이 생길 수 있다.
        제목과 본문의 판별력 있는 검색어가 정확히 일치하는 청크를 함께 반환해, 의미
        라우터가 만든 '겸직·취업규칙' 같은 용어를 벡터 후보 밖에서도 찾을 수 있게 한다.
        """
        if self._index is None:
            raise RuntimeError("FaissStore.load()를 먼저 호출해야 합니다.")
        if top_k <= 0:
            raise ValueError("top_k는 1 이상이어야 합니다.")

        terms = list(
            dict.fromkeys(
                normalized
                for token in query.casefold().split()
                if len(normalized := _normalize_text(token)) >= 2
                and normalized not in GENERIC_SEARCH_TERMS
            )
        )
        if not terms:
            return []

        ranked: list[tuple[int, float, DocumentChunk]] = []
        for chunk in self._chunks:
            metadata = chunk.get("metadata", {})
            searchable = _normalize_text(f"{metadata.get('title', '')} {chunk.get('content', '')}")
            matched_count = sum(term in searchable for term in terms)
            if matched_count == 0:
                continue
            coverage = matched_count / len(terms)
            score = min(0.95, 0.55 + min(matched_count, 3) * 0.1 + coverage * 0.2)
            ranked.append(
                (
                    matched_count,
                    coverage,
                    {
                        "chunk_id": chunk["chunk_id"],
                        "document_id": chunk["document_id"],
                        "title": metadata.get("title", ""),
                        "content": chunk["content"],
                        "score": score,
                        "updated_at": metadata.get("updated_at", ""),
                        "page": metadata.get("page"),
                    },
                )
            )
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in ranked[:top_k]]


def _normalize_text(value: str) -> str:
    """검색 비교에서 띄어쓰기와 문장부호 차이를 제거한다."""
    return "".join(character for character in value.casefold() if character.isalnum())
