"""외부 서비스 없이 각 테스트를 격리하는 공통 pytest fixture."""

import pytest

from app.cache.repository import cache


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    """프로세스 전역 개발 cache가 테스트 순서에 영향을 주지 않게 초기화한다."""
    cache._store.clear()
    cache._expires_at.clear()
