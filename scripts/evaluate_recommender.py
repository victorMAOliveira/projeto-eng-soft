"""Offline evaluation of the recommender on the SYNTHETIC labelled dataset.

Compares the hybrid recommender against two baselines required by the
project (random and filters-only) and two ablations (content-only and
attributes-only), reporting precision@5 and nDCG@5 (graded gains 2^rel − 1).

Outputs ``docs/relatorio/generated/eval_metrics.{md,json}``.
Usage: ``python scripts/evaluate_recommender.py`` (``make eval``).
"""

import json
import math
import random
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "recommendation-service"))
sys.path.insert(0, str(ROOT / "scripts"))

from recommendation_service.recommender import (  # noqa: E402
    OfferFeatures,
    StudentFeatures,
    Weights,
    hard_filter_reasons,
    recommend_for_student,
)
from synthetic_data import load  # noqa: E402

K = 5
RANDOM_RUNS = 30
OUT_DIR = ROOT / "docs" / "relatorio" / "generated"


def precision_at_k(ranked: list[str], rel: dict[str, int], k: int = K) -> float:
    """Share of the top-k items with relevance > 0."""
    return sum(1 for item in ranked[:k] if rel.get(item, 0) > 0) / k


def ndcg_at_k(ranked: list[str], rel: dict[str, int], k: int = K) -> float:
    """Normalised discounted cumulative gain with graded gains ``2^rel − 1``."""

    def dcg(gains: list[int]) -> float:
        return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(gains[:k]))

    ideal = dcg(sorted(rel.values(), reverse=True))
    return dcg([rel.get(item, 0) for item in ranked]) / ideal if ideal else 0.0


def main() -> int:
    """Run every strategy and write the metrics table."""
    dataset = load()
    offers = [
        OfferFeatures(
            id=i,
            title=v.title,
            description=v.description,
            requirements=v.requirements,
            course=v.course,
            min_semester=v.min_semester,
            hours_per_day=v.hours_per_day,
            hours_per_week=v.hours_per_week,
            modality=v.modality,
            city=v.city,
            published_at=datetime.fromisoformat(v.published_at),
        )
        for i, v in enumerate(dataset.internships)
    ]
    key_of = {i: v.key for i, v in enumerate(dataset.internships)}
    labels: dict[str, dict[str, int]] = {}
    for label in dataset.labels:
        labels.setdefault(label["student"], {})[label["internship"]] = label["relevance"]

    strategies = {
        "Híbrido (0,50·cos + 0,35·Jaccard + 0,15·pref)": Weights(0.5, 0.35, 0.15),
        "Ablação: só conteúdo (TF-IDF/cosseno)": Weights(1, 0, 0),
        "Ablação: só atributos (Jaccard)": Weights(0, 1, 0),
    }
    results: dict[str, dict[str, list[float]]] = {
        name: {"p": [], "n": []}
        for name in ["Baseline aleatório", "Baseline só filtros (mais recentes)", *strategies]
    }
    evaluated = 0
    for index, s in enumerate(dataset.students):
        rel = labels.get(s.key, {})
        if not rel or not s.skills:
            continue
        evaluated += 1
        student = StudentFeatures(
            id=index,
            name=s.name,
            course=s.course,
            semester=s.semester,
            skills=s.skills,
            summary=s.resume_summary,
            weekly_hours=s.weekly_availability_hours,
            modality=s.preferred_modality,
            city=s.city,
        )
        for name, weights in strategies.items():
            ranked, _ = recommend_for_student(student, offers, k=K, weights=weights)
            keys = [key_of[r.item_id] for r in ranked]
            results[name]["p"].append(precision_at_k(keys, rel))
            results[name]["n"].append(ndcg_at_k(keys, rel))

        eligible = [o for o in offers if not hard_filter_reasons(student, o)]
        by_recency = sorted(eligible, key=lambda o: (o.published_at, -o.id), reverse=True)
        keys = [key_of[o.id] for o in by_recency[:K]]
        results["Baseline só filtros (mais recentes)"]["p"].append(precision_at_k(keys, rel))
        results["Baseline só filtros (mais recentes)"]["n"].append(ndcg_at_k(keys, rel))

        p_runs, n_runs = [], []
        for run in range(RANDOM_RUNS):
            sample = random.Random(1000 * index + run).sample(offers, K)
            keys = [key_of[o.id] for o in sample]
            p_runs.append(precision_at_k(keys, rel))
            n_runs.append(ndcg_at_k(keys, rel))
        results["Baseline aleatório"]["p"].append(statistics.mean(p_runs))
        results["Baseline aleatório"]["n"].append(statistics.mean(n_runs))

    rows = [
        {
            "strategy": name,
            "precision_at_5": round(statistics.mean(v["p"]), 3),
            "ndcg_at_5": round(statistics.mean(v["n"]), 3),
        }
        for name, v in results.items()
    ]
    meta = {
        "dataset": dataset.meta["description"],
        "synthetic": True,
        "seed": dataset.meta["seed"],
        "students_evaluated": evaluated,
        "internships": len(offers),
        "k": K,
        "random_runs_per_student": RANDOM_RUNS,
        "label_rule": dataset.meta["label_rule"],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "eval_metrics.json").write_text(
        json.dumps({"meta": meta, "results": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "| Estratégia | Precision@5 | nDCG@5 |",
        "|---|---|---|",
        *[
            f"| {r['strategy']} | {r['precision_at_5']:.3f} | {r['ndcg_at_5']:.3f} |".replace(
                ".", ","
            )
            for r in rows
        ],
    ]
    note = (
        f"\n\nDados **sintéticos** (seed {meta['seed']}): {evaluated} estudantes avaliados, "
        f"{len(offers)} vagas, k = {K}; baseline aleatório = média de {RANDOM_RUNS} sorteios por estudante. "
        f"Rótulos: {meta['label_rule']}.\n"
    )
    (OUT_DIR / "eval_metrics.md").write_text("\n".join(lines) + note, encoding="utf-8")
    print("\n".join(lines) + note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
