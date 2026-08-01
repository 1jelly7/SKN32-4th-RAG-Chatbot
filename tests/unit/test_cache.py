from app.cache.key import make_cache_key
from app.cache.repository import MemoryCache
from app.cache.service import lookup_cached_answer, write_answer_cache


def test_cache_key_changes_by_question() -> None:
    assert make_cache_key({"question": "A"}) != make_cache_key({"question": "B"})


def test_cache_key_changes_by_conversation_context() -> None:
    base = {"question": "A"}
    first = {**base, "conversation_context_hash": "first"}
    second = {**base, "conversation_context_hash": "second"}
    assert make_cache_key(first) != make_cache_key(second)


def test_cache_key_changes_by_all_version_suppliers() -> None:
    base = {
        "question": "A",
        "document_index_version": "documents-v1",
        "database_freshness_bucket": "fresh-1",
        "prompt_version": "prompt-v1",
        "model_id": "model-v1",
    }
    for field in (
        "document_index_version",
        "database_freshness_bucket",
        "prompt_version",
        "model_id",
    ):
        changed = {**base, field: "changed"}
        assert make_cache_key(base) != make_cache_key(changed)


def test_cache_service_wraps_graph_execution() -> None:
    repository = MemoryCache()
    state = {
        "question": "A",
        "route": "GENERAL",
    }
    assert lookup_cached_answer(state, repository) is None

    state["answer"] = "ok"
    assert write_answer_cache(state, repository) is True

    repeated_state = {
        "question": "A",
    }
    assert lookup_cached_answer(repeated_state, repository) == {
        "answer": "ok",
        "sources": [],
        "tables": [],
        "route": "GENERAL",
    }
