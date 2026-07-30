import pytest
from app.cache.repository import cache
@pytest.fixture(autouse=True)
def clear_cache():
    cache._store.clear()
