"""Benchmark every retrieval model against the judgments. TODO(WS3).

Intended output - one markdown table for the report:

    model   | P@5   | R@5   | F1@5  | MRR   | nDCG@10
    bm25    | ...   | ...   | ...   | ...   | ...
    tfidf   | ...
    boolean | ...
    dense   | ...
    hybrid  | ...

For each query in queries.jsonl: call retrieval.service.search(model=...),
map result document_ids back to documents.file_hash, feed metrics.py, then
macro-average over queries.

Run with: uv run python -m wadr.evaluation.run_eval
"""


def main() -> None:
    raise NotImplementedError("TODO(WS3): evaluation harness")


if __name__ == "__main__":
    main()
