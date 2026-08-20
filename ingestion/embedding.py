"""
문서 인덱싱 전용 embedding 어댑터.

세 가지 백엔드를 지원합니다:
- "local"(기본값): 문자 n-gram 해싱. API/모델 다운로드 불필요, 완전 오프라인.
  다만 "의미"를 이해하지 못하고 글자 겹침만 보기 때문에, 점수가 낮고(0.1~0.4대)
  질문 표현이 문서 원문과 다르면 관련 있는 내용도 놓칠 수 있습니다.
- "sbert": sentence-transformers 로컬 모델. 최초 실행 시 모델을 한 번 다운로드하면
  이후엔 API 호출 없이 오프라인으로 동작합니다. "local"보다 훨씬 정확한 의미 기반
  검색이 가능하지만, 모델 로딩 시간과 메모리를 씁니다.
- "openai": OpenAI Embeddings API. 가장 정확하지만 API 비용이 발생합니다.
"""

from __future__ import annotations

import hashlib

import numpy as np

DEFAULT_DIMENSION = 384

# sbert 백엔드의 기본 모델입니다. 한국어에 튜닝된 모델을 사용합니다.
DEFAULT_SBERT_MODEL = "jhgan/ko-sroberta-multitask"


class EmbeddingClient:
    """문서 인덱싱 전용 embedding 어댑터. backend에 따라 local/sbert/openai로 동작합니다."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "local-ngram",
        dimension: int = DEFAULT_DIMENSION,
        backend: str = "local",
        sbert_model_name: str = DEFAULT_SBERT_MODEL,
    ) -> None:
        """백엔드에 맞는 내부 클라이언트를 준비한다.

        local 백엔드는 api_key 없이 즉시 동작한다. sbert는 최초 호출 시(지연 로딩)
        sentence-transformers 모델을 로드하므로, import 시점에는 무거운 작업을
        하지 않는다. openai는 api_key가 필요하다.
        """
        self._api_key = api_key
        self._model = model
        self._dimension = dimension
        self._backend = backend.lower()
        self._sbert_model_name = sbert_model_name
        self._sbert_model = None  # 지연 로딩

    @property
    def dimension(self) -> int:
        """모든 입력 벡터에 적용되는 차원을 반환한다. sbert는 실제 모델 차원을 따른다."""
        if self._backend == "sbert":
            self._ensure_sbert_loaded()
            return self._sbert_model.get_sentence_embedding_dimension()
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        """입력 순서를 보존해 각 비어 있지 않은 텍스트의 벡터를 반환한다."""
        for text in texts:
            if not text.strip():
                raise ValueError("빈 텍스트는 임베딩할 수 없습니다. 상위 단계에서 걸러야 합니다.")

        if self._backend == "sbert":
            return self._embed_sbert(texts)
        if self._backend == "openai":
            return self._embed_openai(texts)
        return [self._embed_local(text) for text in texts]

    # ------------------------------------------------------------------
    # local (n-gram 해싱) — 기존 구현
    # ------------------------------------------------------------------
    def _embed_local(self, text: str) -> list[float]:
        """문자 2-gram/3-gram을 해싱해 고정 차원 벡터를 만들고 L2 정규화합니다."""
        vector = np.zeros(self._dimension, dtype=np.float32)
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

    # ------------------------------------------------------------------
    # sbert (sentence-transformers 로컬 모델)
    # ------------------------------------------------------------------
    def _ensure_sbert_loaded(self) -> None:
        if self._sbert_model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers가 설치되어 있지 않습니다. "
                "`pip install sentence-transformers`를 실행한 뒤 다시 시도하세요."
            ) from exc
        self._sbert_model = SentenceTransformer(self._sbert_model_name)

    def _embed_sbert(self, texts: list[str]) -> list[list[float]]:
        self._ensure_sbert_loaded()
        vectors = self._sbert_model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vectors.tolist()

    # ------------------------------------------------------------------
    # openai
    # ------------------------------------------------------------------
    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        if not self._api_key:
            raise RuntimeError("EMBEDDING_BACKEND=openai인데 OPENAI_API_KEY가 비어 있습니다.")
        from openai import OpenAI

        client = OpenAI(api_key=self._api_key)
        response = client.embeddings.create(model=self._model or "text-embedding-3-small", input=texts)
        return [item.embedding for item in response.data]


_default_client: EmbeddingClient | None = None


def _get_default_client() -> EmbeddingClient:
    global _default_client
    if _default_client is None:
        try:
            from app.core.config import get_settings

            settings = get_settings()
            _default_client = EmbeddingClient(
                api_key=settings.openai_api_key,
                model=getattr(settings, "openai_embedding_model", "text-embedding-3-small"),
                dimension=settings.local_embedding_dimension,
                backend=settings.embedding_backend,
                sbert_model_name=getattr(settings, "sbert_model_name", DEFAULT_SBERT_MODEL),
            )
        except Exception:
            # 설정을 못 읽는 환경(예: 단위 테스트)에서도 기본값(local)으로 동작하게 합니다.
            _default_client = EmbeddingClient()
    return _default_client


def embed(texts: list[str]) -> list[list[float]]:
    """설정된 EmbeddingClient(backend에 따라 local/sbert/openai)로 위임하는 편의 함수."""
    return _get_default_client().embed(texts)
