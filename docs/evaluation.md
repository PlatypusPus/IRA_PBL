# Evaluation

```sh
uv run python -m wadr.evaluation.run_eval    # model x metric table for the report
```

## Judgments

Relevance judgments live in `evaluation/queries.jsonl`, with the format
documented in `src/wadr/evaluation/judgments.py`. They are keyed by
`file_hash`, not by row id, so they survive a database wipe and re-ingest.

## Metrics

Precision@k, Recall, F1, MRR and nDCG are hand implemented in
`src/wadr/evaluation/metrics.py`. No sklearn, no pytrec_eval. That is a hard
rule, checked in review, because these are the numbers the report claims we
computed ourselves.

Every model is scored over the same judged query set, so the table compares
like with like.
