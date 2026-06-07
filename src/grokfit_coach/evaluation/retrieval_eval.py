"""Simple retrieval quality evaluation using the golden set.

Computes hit@k and MRR.

Usage:
    python -m grokfit_coach.evaluation.retrieval_eval
"""

from __future__ import annotations

import json
from typing import Any

from grokfit_coach.config.settings import get_settings
from grokfit_coach.rag.retriever import retrieve_exercises


def _load_golden(settings: Any | None = None) -> list[dict]:
    s = settings or get_settings()
    path = s.seeds_dir / "golden_retrieval.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def hit_rate_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    top_k = retrieved_ids[:k]
    return 1.0 if any(r in top_k for r in relevant_ids) else 0.0


def mean_reciprocal_rank(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    for rank, rid in enumerate(retrieved_ids, 1):
        if rid in relevant_ids:
            return 1.0 / rank
    return 0.0


def run_eval(k: int = 5, settings: Any | None = None) -> dict[str, float]:
    golden = _load_golden(settings)
    hits = []
    mrrs = []

    for case in golden:
        query = case["query"]
        relevant = case["relevant_ids"]
        results = retrieve_exercises(query, k=k, settings=settings)
        retrieved_ids = [ex.id for ex in results]
        hits.append(hit_rate_at_k(retrieved_ids, relevant, k))
        mrrs.append(mean_reciprocal_rank(retrieved_ids, relevant))

    return {
        f"hit@{k}": sum(hits) / len(hits) if hits else 0.0,
        "mrr": sum(mrrs) / len(mrrs) if mrrs else 0.0,
        "num_queries": len(golden),
    }


def main() -> None:
    print("Running retrieval evaluation (k=5)...")
    metrics = run_eval(k=5)
    print("Retrieval metrics:")
    for name, val in metrics.items():
        print(f"  {name}: {val:.3f}")


if __name__ == "__main__":
    main()
