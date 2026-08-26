# -*- coding: utf-8 -*-
"""RAG 검색 평가용 qrels(query relevance judgments) 초안을 자동 생성합니다.

`docs/RAG_검색_평가_Ground_Truth_라벨링_가이드.md`(팀 공유 문서)의 방법론을 그대로
코드화한 것입니다:
    1. 질문마다 하이브리드 검색(벡터+어휘)으로 상위 N개 후보 chunk를 모은다.
    2. 각 (질문, chunk) 쌍을 LLM judge에게 보여 0~3 관련성 점수 + 근거를 받는다.
    3. 사람이 검토·수정할 수 있는 CSV(qrels 확장 형식)로 저장한다.

이 스크립트는 "초안"만 만듭니다. 문서 5절의 rubric대로, 2점·3점 판정과 애매한
사례는 반드시 사람이 검토해야 합니다 - LLM 라벨을 그대로 golden set으로 쓰지 마세요.

입력 질문 목록 형식 (CSV, 헤더 필수):
    query_id,query
    Q_001,연차는 입사 후 언제부터 사용할 수 있나요?
    Q_002,법인카드 한도는 얼마인가요?

실행:
    python scripts/rag_ground_truth_label.py <질문목록.csv> <출력.csv> [--top-n 30]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

from openai import RateLimitError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

QREL_FIELDNAMES = [
    "query_id", "query", "chunk_id", "document_id", "relevance",
    "labeler", "reason", "version",
]

# 팀 공유 문서 9절의 LLM judge 프롬프트를 그대로 사용합니다.
JUDGE_SYSTEM_PROMPT = (
    "당신은 RAG 검색 평가 라벨러입니다. 질문에 대한 후보 chunk의 검색 관련성을 "
    "0~3 정수로 평가하세요.\n"
    "0: 질문의 답이나 근거와 무관하다.\n"
    "1: 같은 주제/키워드를 다루지만 질문에 답하기에는 부족하다.\n"
    "2: 질문의 중요한 부분을 답하지만, 조건·예외·세부 정보가 부족하거나 다른 "
    "chunk와 결합해야 한다.\n"
    "3: 질문의 핵심을 직접 답하며, 이 chunk만으로 신뢰할 수 있는 답변 근거가 된다.\n\n"
    "주의:\n"
    "- 단순 키워드 일치가 아니라 질문의 의도와 조건 충족 여부를 판단한다.\n"
    "- 문서에 없는 사실을 추론하지 않는다.\n"
    "- 정책의 대상, 시점, 예외 조건이 다르면 높은 점수를 주지 않는다.\n\n"
    '다음 JSON만 출력하세요(다른 텍스트 금지): '
    '{"relevance": 0, "reason": "20자 이상 100자 이하의 한국어 근거"}'
)


def _read_queries(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or {"query_id", "query"} - set(reader.fieldnames):
            raise ValueError("질문 목록 CSV는 query_id, query 컬럼이 필요합니다.")
        return [row for row in reader if row.get("query", "").strip()]


async def _judge_one(
    client, model: str, query: str, chunk_text: str, semaphore: asyncio.Semaphore
) -> tuple[int, str]:
    """chunk 하나에 대한 LLM judge 점수를 받는다.

    semaphore로 동시 호출 수를 제한하고, RateLimitError(429)는 진짜 실패가
    아니라 "너무 빨리 많이 불러서" 생기는 일시적 문제이므로 지수 백오프로
    재시도한다. 그 외 예외(JSON 파싱 실패 등)만 0점+실패 사유로 안전하게
    폴백한다 - 재시도해도 안 될 문제이기 때문이다.

    실제 사고 재현(2026-08-25): 질문 하나당 후보 30개를 세마포어 없이
    asyncio.gather()로 전부 동시에 호출했더니, 100문항 x 30후보 = 3000건이
    한꺼번에 몰려서 OpenAI RateLimitError가 대량 발생했고, 그게 전부 조용히
    0점으로 깔려서 "진짜 무관"과 "그냥 호출 실패"가 qrels에서 구분이 안 됐다.
    """
    max_retries = 5
    backoff_seconds = 1.0

    async with semaphore:
        for attempt in range(max_retries):
            user_content = f"[사용자 질문]\n{query}\n\n[후보 chunk]\n{chunk_text[:2000]}"
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0,
                    response_format={"type": "json_object"},
                )
                payload = json.loads(response.choices[0].message.content or "{}")
                relevance = int(payload.get("relevance", 0))
                if relevance not in (0, 1, 2, 3):
                    raise ValueError(f"관련성 점수가 0~3 범위를 벗어남: {relevance}")
                reason = str(payload.get("reason", ""))[:200]
                return relevance, reason
            except RateLimitError:
                if attempt == max_retries - 1:
                    return 0, "[LLM judge 실패 - 재시도 5회 후에도 RateLimitError, 사람 검토 필요]"
                await asyncio.sleep(backoff_seconds)
                backoff_seconds *= 2
            except Exception as exc:  # noqa: BLE001 - 라벨링 초안이라 한 건 실패로 전체를 막지 않는다
                return 0, f"[LLM judge 실패 - 사람 검토 필요: {type(exc).__name__}]"

    return 0, "[LLM judge 실패 - 도달할 수 없는 경로]"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queries_csv", type=Path, help="query_id,query 컬럼을 가진 입력 CSV")
    parser.add_argument("output_csv", type=Path, help="qrels 초안을 저장할 출력 CSV")
    parser.add_argument("--top-n", type=int, default=30, help="질문당 후보 chunk 수 (기본 30)")
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="LLM judge 동시 호출 수 상한 (기본 5) - 너무 높이면 RateLimitError가 다시 대량 발생함",
    )
    args = parser.parse_args()

    from app.core.config import get_settings
    from mcp_servers.document_tools.faiss_store import FaissStore
    from ingestion.embedding import embed

    settings = get_settings()
    queries = _read_queries(args.queries_csv)
    if not queries:
        print("질문이 하나도 없습니다. CSV를 확인하세요.")
        sys.exit(1)

    index_path = Path(settings.faiss_path) / "index.faiss"
    store = FaissStore(index_path)
    metadata = store.load()
    index_version = metadata["index_version"]
    print(f"인덱스 버전: {index_version}, 청크 수: {metadata['chunk_count']}")
    print(f"질문 {len(queries)}개 x 후보 최대 {args.top_n}개 -> LLM judge 호출 시작\n")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    semaphore = asyncio.Semaphore(args.max_concurrent)

    rows: list[dict[str, str]] = []
    for i, item in enumerate(queries, start=1):
        query_id, query = item["query_id"], item["query"]
        print(f"[{i}/{len(queries)}] {query_id}: {query}")

        query_vector = embed([query])[0]
        vector_candidates = store.search(query_vector, args.top_n)
        lexical_candidates = store.search_text(query, args.top_n)
        merged: dict[str, dict] = {}
        for candidate in vector_candidates + lexical_candidates:
            current = merged.get(candidate["chunk_id"])
            if current is None or candidate["score"] > current["score"]:
                merged[candidate["chunk_id"]] = candidate
        candidates = sorted(merged.values(), key=lambda c: c["score"], reverse=True)[: args.top_n]

        if not candidates:
            print("  후보 없음 - 건너뜀 (검색 자체가 안 되는 질문일 수 있음, 확인 필요)")
            continue

        # semaphore가 동시 호출 수를 max_concurrent로 제한한다 - 질문 하나에 30개
        # 후보가 있어도, 실제로는 한 번에 max_concurrent개씩만 API를 부른다.
        judged = await asyncio.gather(
            *[
                _judge_one(client, settings.openai_model, query, candidate["content"], semaphore)
                for candidate in candidates
            ]
        )
        for candidate, (relevance, reason) in zip(candidates, judged):
            rows.append(
                {
                    "query_id": query_id,
                    "query": query,
                    "chunk_id": candidate["chunk_id"],
                    "document_id": candidate["document_id"],
                    "relevance": str(relevance),
                    "labeler": "llm-judge",
                    "reason": reason,
                    "version": index_version,
                }
            )
        scored = sorted(zip(candidates, judged), key=lambda pair: pair[1][0], reverse=True)
        top = scored[0]
        print(f"  최고점: {top[1][0]}점 - {top[0].get('title', '')[:30]}")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=QREL_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n완료: {args.output_csv} 에 {len(rows)}개 (질문,chunk) 라벨 저장됨.")
    print("주의: relevance 2~3점과 애매한 사례는 반드시 사람이 검토한 뒤 golden set으로 확정하세요.")


if __name__ == "__main__":
    asyncio.run(main())