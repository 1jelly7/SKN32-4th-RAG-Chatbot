"""질문 원문이나 근거를 노출하지 않는 요청 단계별 성능 계측 도구."""

from __future__ import annotations

import logging
import time
from collections.abc import MutableMapping
from typing import Any

from app.logging.context import get_request_id

logger = logging.getLogger(__name__)


def start_timer() -> int:
    """단조 시계 기반 측정 시작값을 반환한다."""
    return time.perf_counter_ns()


def elapsed_ms(started_ns: int) -> float:
    """시작값부터 현재까지 경과 시간을 밀리초로 반환한다."""
    return round((time.perf_counter_ns() - started_ns) / 1_000_000, 3)


def record_timing(
    timings: MutableMapping[str, float], stage: str, started_ns: int
) -> float:
    """단계 시간을 누적해 재시도와 복수 Tool 호출도 한 값으로 보존한다."""
    duration = elapsed_ms(started_ns)
    timings[stage] = round(timings.get(stage, 0.0) + duration, 3)
    return duration


def server_timing_header(timings: MutableMapping[str, float]) -> str:
    """브라우저 Performance API가 읽을 수 있는 Server-Timing 값을 만든다."""
    return ", ".join(
        f"{stage};dur={duration:.3f}"
        for stage, duration in timings.items()
        if stage.replace("_", "").isalnum() and duration >= 0
    )


def log_llm_completion(call_type: str, model: str, started_ns: int, response: Any) -> None:
    """응답 본문 없이 LLM 지연과 사용 가능한 token 수만 기록한다."""
    usage = getattr(response, "usage", None)
    logger.info(
        "request_id=%s call_type=%s model=%s elapsed_ms=%.3f attempts=1 input_tokens=%s output_tokens=%s",
        get_request_id(),
        call_type,
        model,
        elapsed_ms(started_ns),
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
        extra={"event": "llm_call_completed"},
    )
