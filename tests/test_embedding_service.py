# -*- coding: utf-8 -*-
"""EmbeddingService의 로컬 임베딩 동작을 검증합니다."""

import math

import pytest

from app.config.settings import Settings
from app.llm.embedding_service import EmbeddingService


@pytest.fixture
def local_settings():
    """API 키 없이 로컬 백엔드만 쓰는 설정을 만듭니다."""
    return Settings(embedding_backend="local", openai_api_key="", local_embedding_dimension=64)


def test_local_embedding_dimension_matches_settings(local_settings):
    service = EmbeddingService(local_settings)
    vector = service.embed_query("테스트 문장입니다")
    assert len(vector) == local_settings.local_embedding_dimension


def test_local_embedding_is_deterministic(local_settings):
    """같은 텍스트는 항상 같은 벡터를 만들어야 검색 결과가 재현 가능합니다."""
    service = EmbeddingService(local_settings)
    v1 = service.embed_query("법인카드 사용 기준")
    v2 = service.embed_query("법인카드 사용 기준")
    assert v1 == v2


def test_local_embedding_is_normalized(local_settings):
    """벡터 길이가 1에 가까워야 코사인 유사도 검색이 의도대로 동작합니다."""
    service = EmbeddingService(local_settings)
    vector = service.embed_query("아무 문장이나 넣어봅니다")
    norm = math.sqrt(sum(v * v for v in vector))
    assert norm == pytest.approx(1.0, abs=1e-5)


def test_local_embedding_similar_text_scores_higher_than_unrelated():
    """조사가 다른 같은 단어(법인카드는/법인카드를)가 무관한 단어보다 더 비슷해야 합니다."""
    settings = Settings(embedding_backend="local", openai_api_key="", local_embedding_dimension=256)
    service = EmbeddingService(settings)

    a = service.embed_query("법인카드는 어떻게 사용하나요")
    b = service.embed_query("법인카드를 사용하는 기준")
    c = service.embed_query("오늘 점심 메뉴 추천해줘")

    def cosine(x, y):
        return sum(i * j for i, j in zip(x, y))

    assert cosine(a, b) > cosine(a, c)


def test_embed_documents_batch_returns_same_count(local_settings):
    service = EmbeddingService(local_settings)
    texts = ["문장 하나", "문장 둘", "문장 셋"]
    vectors = service.embed_documents(texts)
    assert len(vectors) == len(texts)


def test_openai_backend_without_key_raises_clear_error():
    """API 키 없이 openai 백엔드를 강제로 쓰면 명확한 에러가 나야 합니다."""
    settings = Settings(embedding_backend="openai", openai_api_key="")
    service = EmbeddingService(settings)
    with pytest.raises(RuntimeError):
        service.embed_query("테스트")
