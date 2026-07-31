import pytest
from app.cache.repository import cache
@pytest.mark.integration
def test_cache_roundtrip():
    cache.set('x', {'answer':'ok'}); assert cache.get('x')['answer'] == 'ok'
