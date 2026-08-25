"""성능 계측 header와 통계 계산의 결정적 계약."""

from scripts.benchmark_chat_performance import parse_server_timing, summarize


def test_parse_server_timing_ignores_malformed_values() -> None:
    assert parse_server_timing("cache_lookup;dur=1.25, invalid, app_total;dur=9") == {
        "cache_lookup": 1.25,
        "app_total": 9.0,
    }


def test_summarize_uses_nearest_rank_p95() -> None:
    assert summarize([1, 2, 3, 4, 10]) == {
        "min": 1,
        "avg": 4,
        "median": 3,
        "p95": 10,
        "max": 10,
    }
