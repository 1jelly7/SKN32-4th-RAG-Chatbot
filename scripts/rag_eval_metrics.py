# -*- coding: utf-8 -*-
"""qrels(query relevance judgments) CSV를 기준으로 실제 검색 결과의 품질을
Recall@k, Precision@k, MRR, nDCG@k로 측정합니다.

`docs/RAG_검색_평가_Ground_Truth_라벨링_가이드.md`(팀 공유 문서) 8절의 지표 정의를
그대로 구현했습니다. relevance >= 2를 "정답 근거"로 보는 기준(문서 8절 권장)을
기본값으로 쓰되, --relevance-threshold로 바꿀 수 있습니다.

qrels CSV는 scripts/rag_ground_truth_label.py가 만든 초안이든, 사람이 검토해
확정한 golden set이든 상관없이 query_id, query, chunk_id, relevance 컬럼만
있으면 됩니다.

주의: qrels에 없는(사람이 라벨을 안 남긴) chunk가 검색 결과에 나오면 관련성
0으로 취급합니다 - 이건 표준 IR 관례지만, 후보 pool을 좁게 잡았다면(예: top-30
로만 라벨링) 진짜 정답인데 라벨이 없어서 0으로 깎이는 chunk가 있을 수 있다는
걸 감안해서 해석하세요(문서 3단계 "후보 chunk 좁히기" 참고).

실행:
    python scripts/rag_eval_metrics.py <qrels.csv> [--k 5,10] [--relevance-threshold 2]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _read_qrels(path: Path) -> dict[str, dict]:
    """query_id -> {"query": str, "relevance": {chunk_id: int}} 형태로 읽는다."""
    queries: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"query_id", "query", "chunk_id", "relevance"}
        if reader.fieldnames is None or required - set(reader.fieldnames):
            raise ValueError(f"qrels CSV는 {required} 컬럼이 필요합니다.")
        for row in reader:
            query_id = row["query_id"]
            entry = queries.setdefault(query_id, {"query": row["query"], "relevance": {}})
            entry["relevance"][row["chunk_id"]] = int(row["relevance"])
    return queries


async def _retrieve_ranked_chunk_ids(store, query: str, top_k: int) -> list[str]:
    """운영 경로(rag.py::retrieve)와 동일한 벡터+어휘 하이브리드 병합 로직."""
    from ingestion.embedding import embed

    query_vector = embed([query])[0]
    vector_candidates = store.search(query_vector, top_k * 5)
    lexical_candidates = store.search_text(query, top_k * 5)
    merged: dict[str, dict] = {}
    for candidate in vector_candidates + lexical_candidates:
        current = merged.get(candidate["chunk_id"])
        if current is None or candidate["score"] > current["score"]:
            merged[candidate["chunk_id"]] = candidate
    ranked = sorted(merged.values(), key=lambda c: c["score"], reverse=True)[:top_k]
    return [c["chunk_id"] for c in ranked]


def _recall_at_k(ranked: list[str], relevance: dict[str, int], k: int, threshold: int) -> float:
    top_k = ranked[:k]
    has_hit = any(relevance.get(chunk_id, 0) >= threshold for chunk_id in top_k)
    return 1.0 if has_hit else 0.0


def _precision_at_k(ranked: list[str], relevance: dict[str, int], k: int, threshold: int) -> float:
    top_k = ranked[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for chunk_id in top_k if relevance.get(chunk_id, 0) >= threshold)
    return hits / len(top_k)


def _mrr(ranked: list[str], relevance: dict[str, int], threshold: int) -> float:
    for rank, chunk_id in enumerate(ranked, start=1):
        if relevance.get(chunk_id, 0) >= threshold:
            return 1.0 / rank
    return 0.0


def _ndcg_at_k(ranked: list[str], relevance: dict[str, int], k: int) -> float:
    """graded relevance(0~3)를 그대로 쓰는 표준 nDCG."""
    top_k = ranked[:k]
    dcg = sum(
        relevance.get(chunk_id, 0) / math.log2(rank + 1)
        for rank, chunk_id in enumerate(top_k, start=1)
    )
    ideal_grades = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum(grade / math.log2(rank + 1) for rank, grade in enumerate(ideal_grades, start=1))
    return dcg / idcg if idcg > 0 else 0.0


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qrels_csv", type=Path)
    parser.add_argument("--k", type=str, default="5,10", help="쉼표로 구분된 k 목록 (기본 5,10)")
    parser.add_argument(
        "--relevance-threshold",
        type=int,
        default=2,
        help="Recall/Precision/MRR에서 '정답 근거'로 볼 최소 relevance (기본 2, 문서 8절 권장)",
    )
    args = parser.parse_args()
    ks = [int(k.strip()) for k in args.k.split(",") if k.strip()]
    max_k = max(ks)

    from app.core.config import get_settings
    from mcp_servers.document_tools.faiss_store import FaissStore

    settings = get_settings()
    index_path = Path(settings.faiss_path) / "index.faiss"
    store = FaissStore(index_path)
    store.load()

    queries = _read_qrels(args.qrels_csv)
    if not queries:
        print("qrels에 질문이 없습니다.")
        sys.exit(1)

    metrics: dict[str, list[float]] = defaultdict(list)
    no_positive_queries: list[str] = []

    for query_id, entry in queries.items():
        relevance = entry["relevance"]
        if not any(v >= args.relevance_threshold for v in relevance.values()):
            no_positive_queries.append(query_id)

        ranked = await _retrieve_ranked_chunk_ids(store, entry["query"], max_k)

        for k in ks:
            metrics[f"Recall@{k}"].append(_recall_at_k(ranked, relevance, k, args.relevance_threshold))
            metrics[f"Precision@{k}"].append(_precision_at_k(ranked, relevance, k, args.relevance_threshold))
            metrics[f"nDCG@{k}"].append(_ndcg_at_k(ranked, relevance, k))
        metrics["MRR"].append(_mrr(ranked, relevance, args.relevance_threshold))

    print("=" * 70)
    print(f"질문 수: {len(queries)}  |  relevance >= {args.relevance_threshold} 를 정답 근거로 판정")
    print("=" * 70)
    for name, values in metrics.items():
        avg = sum(values) / len(values)
        print(f"{name:15s} = {avg:.3f}")

    if no_positive_queries:
        print(f"\n경고: qrels 안에 relevance >= {args.relevance_threshold}인 chunk가 하나도 없는 "
              f"질문이 {len(no_positive_queries)}개 있습니다(전부 0점 처리됨):")
        for query_id in no_positive_queries[:10]:
            print(f"  - {query_id}: {queries[query_id]['query']}")
        print("이 질문들은 후보 pool 자체에 정답이 없었거나(검색기 실패), 라벨링이 "
              "덜 됐을 수 있습니다 - 문서 7절 3단계(원문 탐색으로 누락 정답 추가)를 참고하세요.")


if __name__ == "__main__":
    asyncio.run(main())
