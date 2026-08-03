"""실제 LLM/MCP/DB 경계를 사용하는 로컬 채팅 성능 벤치마크.

인증만 비식별 메모리 계정으로 대체한다. 질문·응답·세션 토큰은 출력하지 않고,
HTTP 상태와 cache/route/timing 통계만 JSON으로 기록한다.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.models import Account
from app.auth.passwords import hash_password
from app.auth.repository import MemoryAccountRepository
from app.auth.service import AuthenticationService
from app.cache.repository import MemoryCache
from app.core.dependencies import AppDependencies
from app.main import create_app

BENCHMARK_PASSWORD = "local-performance-only"
BENCHMARK_SECRET = "local-performance-benchmark-secret-key"


@dataclass(frozen=True)
class Scenario:
    """권한·route·질문을 함께 고정한 측정 시나리오."""

    name: str
    username: str
    question: str


SCENARIOS = (
    Scenario("general", "admin", "바나나는 무슨 색인가?"),
    Scenario("document", "hr", "법인카드 규정 알려줘"),
    Scenario("database", "finance", "공급업체별 구매 지출을 알려줘"),
    Scenario("both", "finance", "법인카드 지침과 공급업체별 구매 지출을 함께 알려줘"),
)


def build_benchmark_application() -> FastAPI:
    """실제 provider와 비식별 로컬 RBAC 계정을 조립한 localhost 전용 앱을 만든다."""
    password_hash = hash_password(BENCHMARK_PASSWORD)
    repository = MemoryAccountRepository(
        [
            Account(9101, "admin", password_hash, "Benchmark Admin", "admin", True),
            Account(9102, "hr", password_hash, "Benchmark HR", "hr", True),
            Account(9103, "finance", password_hash, "Benchmark Finance", "finance", True),
        ]
    )
    dependencies = AppDependencies(
        cache=MemoryCache(),
        auth_service=AuthenticationService(repository),
        auth_secret=BENCHMARK_SECRET,
        configure_logging=lambda: None,
        warmup_providers=True,
    )
    return create_app(dependencies)


benchmark_app = build_benchmark_application()


def parse_server_timing(value: str) -> dict[str, float]:
    """Server-Timing header의 stage별 duration을 숫자로 변환한다."""
    timings: dict[str, float] = {}
    for item in value.split(","):
        parts = [part.strip() for part in item.split(";")]
        if len(parts) != 2 or not parts[1].startswith("dur="):
            continue
        try:
            timings[parts[0]] = float(parts[1].removeprefix("dur="))
        except ValueError:
            continue
    return timings


def summarize(values: list[float]) -> dict[str, float]:
    """최소·평균·중앙값·nearest-rank p95·최대값을 반환한다."""
    ordered = sorted(values)
    p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return {
        "min": round(ordered[0], 3),
        "avg": round(statistics.fmean(ordered), 3),
        "median": round(statistics.median(ordered), 3),
        "p95": round(ordered[p95_index], 3),
        "max": round(ordered[-1], 3),
    }


def _login(client: TestClient, username: str) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": BENCHMARK_PASSWORD},
    )
    if response.status_code != 200:
        raise RuntimeError(f"benchmark login failed: status={response.status_code}")


def run_scenario(client: TestClient, scenario: Scenario, iterations: int) -> dict[str, Any]:
    """고유 conversation miss와 동일 conversation hit를 각각 반복 측정한다."""
    _login(client, scenario.username)
    misses: list[dict[str, Any]] = []
    for index in range(iterations):
        started_ns = time.perf_counter_ns()
        response = client.post(
            "/api/chat",
            json={"question": scenario.question, "session_id": f"{scenario.name}-miss-{index}"},
        )
        e2e_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        body = response.json()
        misses.append(
            {
                "status": response.status_code,
                "cached": body.get("cached"),
                "route": body.get("route"),
                "evidence_status": body.get("evidence_status"),
                "e2e_ms": round(e2e_ms, 3),
                "server": parse_server_timing(response.headers.get("server-timing", "")),
            }
        )

    hit_payload = {"question": scenario.question, "session_id": f"{scenario.name}-hit"}
    client.post("/api/chat", json=hit_payload)
    hits: list[dict[str, Any]] = []
    for _ in range(iterations):
        started_ns = time.perf_counter_ns()
        response = client.post("/api/chat", json=hit_payload)
        e2e_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        body = response.json()
        hits.append(
            {
                "status": response.status_code,
                "cached": body.get("cached"),
                "route": body.get("route"),
                "evidence_status": body.get("evidence_status"),
                "e2e_ms": round(e2e_ms, 3),
                "server": parse_server_timing(response.headers.get("server-timing", "")),
            }
        )

    return {
        "scenario": scenario.name,
        "role": scenario.username,
        "miss": _summarize_runs(misses),
        "hit": _summarize_runs(hits),
    }


def _summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """개별 응답에서 공개 가능한 상태와 시간 통계만 집계한다."""
    stages = sorted({stage for run in runs for stage in run["server"]})
    return {
        "iterations": len(runs),
        "statuses": sorted({run["status"] for run in runs}),
        "cached_values": sorted({str(run["cached"]) for run in runs}),
        "routes": sorted({str(run["route"]) for run in runs}),
        "valid_under_5000": sum(
            run["status"] == 200
            and run["evidence_status"] not in ("INSUFFICIENT", "CONTRADICTED")
            and run["e2e_ms"] <= 5000
            for run in runs
        ),
        "e2e_ms": summarize([run["e2e_ms"] for run in runs]),
        "server_ms": summarize([run["server"].get("app_total", 0.0) for run in runs]),
        "stages_avg_ms": {
            stage: round(statistics.fmean(run["server"].get(stage, 0.0) for run in runs), 3)
            for stage in stages
            if stage != "app_total"
        },
    }


def main() -> None:
    """선택한 실제 경로를 5회 이상 실행하고 JSON 통계를 표준 출력한다."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--scenario", choices=[item.name for item in SCENARIOS] + ["all"], default="all")
    args = parser.parse_args()
    if args.iterations < 5:
        parser.error("--iterations는 5 이상이어야 합니다.")

    selected = SCENARIOS if args.scenario == "all" else tuple(
        item for item in SCENARIOS if item.name == args.scenario
    )
    results: list[dict[str, Any]] = []
    startup_started_ns = time.perf_counter_ns()
    with TestClient(build_benchmark_application()) as client:
        startup_ms = (time.perf_counter_ns() - startup_started_ns) / 1_000_000
        for scenario in selected:
            results.append(run_scenario(client, scenario, args.iterations))
    print(
        json.dumps(
            {
                "measurement": "in_process_http_e2e",
                "provider_warmup_ms": round(startup_ms, 3),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
