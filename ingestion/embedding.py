"""
문서 인덱싱 전용 embedding 어댑터.

기본은 외부 API 호출이 필요 없는 "local" 임베딩입니다. 문자 n-gram을 해싱해서
고정 차원 벡터로 변환하는 방식으로, 조사/어미가 붙어 형태가 조금 달라져도
("법인카드는" vs "법인카드를") 부분 문자열이 겹치면 매칭되어 한국어 문서 검색에
그럭저럭 강합니다. 완전히 오프라인으로 동작하며 API 키가 필요 없습니다.
"""

from __future__ import annotations

import hashlib

import numpy as np

DEFAULT_DIMENSION = 384


class EmbeddingClient:
    """문서 인덱싱 전용 embedding 어댑터. 기본 구현은 로컬(API 미사용)입니다."""

    def __init__(self, api_key: str = "", model: str = "local-ngram", dimension: int = DEFAULT_DIMENSION) -> None:
        """API 키와 embedding 모델을 보관하고 요청 클라이언트를 초기화한다.

        local 백엔드는 api_key가 없어도 동작합니다. api_key는 나중에 OpenAI
        임베딩으로 전환할 때를 대비해 인터페이스만 맞춰둔 것입니다.
        """
        self._api_key = api_key
        self._model = model
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        """입력 순서를 보존해 각 비어 있지 않은 텍스트의 동일 차원 벡터를 반환한다.

        API 실패라는 개념이 없는 로컬 구현이라 재시도/timeout은 필요 없습니다.
        빈 문자열이 포함되어 있으면 명시적으로 실패시킵니다(인덱스 작성 전에
        빈 chunk를 걸러내는 게 정상 흐름이라, 여기 들어오면 상위 단계의 버그입니다).
        """
        vectors: list[list[float]] = []
        for text in texts:
            if not text.strip():
                raise ValueError("빈 텍스트는 임베딩할 수 없습니다. 상위 단계에서 걸러야 합니다.")
            vectors.append(self._embed_one(text))
        return vectors

    def _embed_one(self, text: str) -> list[float]:
        """문자 2-gram/3-gram을 해싱해 고정 차원 벡터를 만들고 L2 정규화합니다."""

        vector = np.zeros(self._dimension, dtype=np.float32)

        # 공백 유무와 무관하게 같은 n-gram이 나오도록 공백을 제거합니다.
        normalized = "".join(text.lower().split())

        tokens: list[str] = []
        for n in (2, 3):
            tokens.extend(normalized[i : i + n] for i in range(max(0, len(normalized) - n + 1)))

        if not tokens:
            return vector.tolist()

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % self._dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = float(np.linalg.norm(vector))
        if norm > 0.0:
            vector = vector / norm

        return vector.tolist()


_default_client: EmbeddingClient | None = None


def _get_default_client() -> EmbeddingClient:
    global _default_client
    if _default_client is None:
        try:
            from app.core.config import get_settings

            settings = get_settings()
            _default_client = EmbeddingClient(dimension=settings.local_embedding_dimension)
        except Exception:
            # 설정을 못 읽는 환경(예: 단위 테스트)에서도 기본값으로 동작하게 합니다.
            _default_client = EmbeddingClient()
    return _default_client


def embed(texts: list[str]) -> list[list[float]]:
    """설정된 EmbeddingClient를 이용하는 편의 함수; import 시 API 호출은 하지 않는다."""
    return _get_default_client().embed(texts)
