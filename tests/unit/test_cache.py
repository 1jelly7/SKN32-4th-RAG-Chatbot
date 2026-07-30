from app.cache.key import make_cache_key
def test_cache_key_changes_by_user():
    assert make_cache_key({'question':'A','user_context':{'user_id':'a'}}) != make_cache_key({'question':'A','user_context':{'user_id':'b'}})
