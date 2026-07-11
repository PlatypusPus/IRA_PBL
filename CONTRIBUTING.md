# Contributing

## Branches

`ws<N>/<short-kebab-description>` — e.g. `ws2/docx-extractor`,
`shared/inverted-index`. `main` stays green: it must always pass
`uv run pytest` and `uv run ruff check .`.

## Pull requests

- One TODO.md checklist item per PR; keep diffs small.
- Tick the TODO.md box **and** unskip the matching test in
  `tests/test_todo_checklist.py` in the same PR.
- One approval from someone outside your workstream.
- No new dependencies without a one-line justification in the PR description.
- Schema changes ship as a new numbered file in `migrations/` — never edit a
  migration that has already been applied somewhere.

## Hard rules (non-negotiable, checked in review)

1. **The engine never imports adapters.** Nothing under `wadr/ingestion`,
   `wadr/indexing`, `wadr/retrieval`, or `wadr/evaluation` may import
   `wadr.adapters`. Dependency points inward only: adapters call the engine,
   never the reverse. Quick check before pushing:
   `grep -r "wadr.adapters" src/wadr/ingestion src/wadr/indexing src/wadr/retrieval src/wadr/evaluation`
   must return nothing.

2. **Classical IR modules stay library-free.** `indexing/inverted_index.py`,
   `retrieval/boolean_model.py`, `retrieval/tfidf_model.py` (numpy allowed
   there only) and `evaluation/metrics.py` use the standard library and
   nothing else. No sklearn, nltk, gensim, rank_bm25, or pytrec_eval — these
   files are viva evidence that we built the classical machinery ourselves.
