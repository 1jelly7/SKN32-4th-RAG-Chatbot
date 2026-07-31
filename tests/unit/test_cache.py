from app.cache.key import make_cache_key
from app.cache.service import lookup_cached_answer, write_answer_cache


def test_cache_key_changes_by_user():
    assert make_cache_key({'question':'A','user_context':{'user_id':'a'}}) != make_cache_key({'question':'A','user_context':{'user_id':'b'}})


def test_cache_key_changes_by_conversation_context():
    base = {"question": "A", "user_context": {"user_id": "a"}}
    first = {**base, "conversation_context_hash": "first"}
    second = {**base, "conversation_context_hash": "second"}
    assert make_cache_key(first) != make_cache_key(second)


def test_cache_service_wraps_graph_execution():
    state = {
        "question": "A",
        "user_context": {"user_id": "a"},
        "route": "GENERAL",
    }
    assert lookup_cached_answer(state) is None

    state["answer"] = "ok"
    assert write_answer_cache(state) is True

    repeated_state = {
        "question": "A",
        "user_context": {"user_id": "a"},
    }
    assert lookup_cached_answer(repeated_state) == {
        "answer": "ok",
        "sources": [],
        "route": "GENERAL",
    }
