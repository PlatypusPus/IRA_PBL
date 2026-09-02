"""Benchmark every retrieval model against the judgments.

Prints one markdown table for the report:

    | model   | P@5 | R@5 | F1@5 | MRR | nDCG@10 |

For each query in queries.jsonl: call retrieval.service.search(model=...),
map result document_ids back to documents.file_hash (judgments are keyed by
hash so they survive a DB wipe), feed metrics.py, then MACRO-average - every
query counts equally, regardless of how many relevant documents it has.

Run with: uv run python -m wadr.evaluation.run_eval [path/to/queries.jsonl]
"""

import os
import sys
from pathlib import Path

from wadr.db import get_conn
from wadr.evaluation import judgments, metrics
from wadr.retrieval import service

MODELS = ["boolean", "tfidf", "bm25", "dense", "hybrid"]
K = 5        # the cut-off for P/R/F1 - what a WhatsApp reply actually shows
NDCG_K = 10  # nDCG gets a deeper look, since it is the rank-aware measure

# Repo root: src/wadr/evaluation/run_eval.py -> parents[3]
DEFAULT_QUERIES = Path(__file__).resolve().parents[3] / "evaluation" / "queries.jsonl"


def evaluate(model: str, rows: list[dict], hash_by_id: dict) -> dict:
    """Run every query through one model and macro-average the metrics."""
    totals = {"P@5": 0.0, "R@5": 0.0, "F1@5": 0.0, "MRR": 0.0, "nDCG@10": 0.0}
    for row in rows:
        hits = service.search(row["query"], model=model, top_k=NDCG_K)
        # results are document ids; judgments are file hashes
        ranked = [hash_by_id.get(hit.document_id) for hit in hits]
        judged = row["relevant"]
        totals["P@5"] += metrics.precision_at_k(ranked, judged, K)
        totals["R@5"] += metrics.recall_at_k(ranked, judged, K)
        totals["F1@5"] += metrics.f1_at_k(ranked, judged, K)
        totals["MRR"] += metrics.reciprocal_rank(ranked, judged)
        totals["nDCG@10"] += metrics.ndcg_at_k(ranked, judged, NDCG_K)
    return {name: total / len(rows) for name, total in totals.items()}


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        os.environ.get("WADR_QUERIES", DEFAULT_QUERIES)
    )
    if not path.exists():
        raise SystemExit(
            f"No judgments at {path}.\n"
            "Create it (one JSON object per line, format in evaluation/judgments.py) "
            "or pass a path: uv run python -m wadr.evaluation.run_eval <file>"
        )
    all_rows = judgments.load(path)
    # An ungraded query scores 0 for every model, which would silently drag the
    # averages toward zero and read as "the models are bad". Only graded
    # queries are evaluated; the header says how many that is.
    rows = [r for r in all_rows if r["relevant"]]
    if not rows:
        raise SystemExit(
            f"None of the {len(all_rows)} queries in {path} carry a relevance "
            "judgment yet. Grade some first: start the API "
            "(uv run uvicorn wadr.api.app:app) and open http://localhost:8000/judge"
        )
    with get_conn() as conn:
        hash_by_id = dict(conn.execute("SELECT id, file_hash FROM documents").fetchall())

    columns = ["P@5", "R@5", "F1@5", "MRR", "nDCG@10"]
    print(f"\n{len(rows)} of {len(all_rows)} queries graded, "
          f"over {len(hash_by_id)} documents\n")
    print("| model   | " + " | ".join(f"{c:>7}" for c in columns) + " |")
    print("|---------|" + "|".join("--------:" for _ in columns) + "|")
    for model in MODELS:
        scores = evaluate(model, rows, hash_by_id)
        print(f"| {model:<7} | " + " | ".join(f"{scores[c]:7.3f}" for c in columns) + " |")
    print()


if __name__ == "__main__":
    main()
