# Retrieval

Pick a model with `--model`. Default is `hybrid`.

```sh
uv run wadr search "tf-idf weighting" --model hybrid --top-k 10
```

## The models

| Model | How it ranks | Notes |
|---|---|---|
| `bm25` | Probabilistic term weighting over chunk text. | Strong exact wording baseline. |
| `dense` | Cosine similarity over `nomic-embed-text` embeddings in pgvector. | Catches paraphrases. Needs Ollama. |
| `hybrid` | Runs BM25 and dense, then fuses the two ranked lists with RRF. | Default, and the one the benchmark reports. |
| `tfidf` | Log normalised tf, log idf, L2 normalised document vectors, cosine score. | From scratch, numpy only. Lab evidence. |
| `boolean` | Set membership over the hand built inverted index. | Unranked by definition: every hit scores 1.0. |

`tfidf` and `boolean` exist to be read, not to win. Their module docstrings
carry the formulas and the reason each one is limited.

## Fusion

Scores from different models are not comparable, so they are never added.
Reciprocal Rank Fusion combines the ranked lists instead:

```
score(d) = sum over lists containing d of 1 / (k + rank_d),   k = 60
```

A document missing from a list contributes nothing for that list.

## Recency boost

A document re-shared today ranks as if it had 1.15x its fused score, and that
edge halves every 30 days. RRF scores are flat by nature (rank 1 beats rank 10
by 1.15x and rank 30 by only 1.48x), so 0.15 moves a same day share about ten
places: enough to break ties and surface a freshly forwarded copy, not enough
to drag rank 30 to the top. Anything near 0.5 overrules relevance outright,
which `test_recency_boost_does_not_overrule` pins down.

## Filters

Filter tokens are stripped from the query before ranking and turned into SQL
constraints. Unknown prefixes fall through and stay part of the query text.

| Token | Constrains | Example |
|---|---|---|
| `from:` | who sent it | `invoice from:dad` |
| `in:` | which chat | `notes in:family` |
| `type:` | mime type suffix | `receipt type:pdf` |
| `before:` | sent before an ISO date | `timetable before:2026-01-01` |
| `after:` | sent after an ISO date | `timetable after:2026-01-01` |

Malformed dates raise `ValueError` rather than being silently ignored.
