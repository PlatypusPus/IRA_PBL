# WADR — Team Assignment Sheet

**All workstreams are implemented and `tests/test_todo_checklist.py` is fully
green — 51 passed, 0 skipped.** No `NotImplementedError` stubs remain in `src/`.
What is left is judgement work, not code: review the relevance grades in
`evaluation/queries.jsonl` and extend it from 24 queries toward ~40.

The history below is kept as the record of who built what, for the report.

Rules that bind everyone are in [CONTRIBUTING.md](CONTRIBUTING.md):
the engine never imports adapters, and classical IR modules stay library-free.

---

## WS1 — WhatsApp integration (Baileys bridge + adapter)

**Context.** WADR's engine does not know WhatsApp exists: adapters hand it raw
bytes through `MessagingInterface.on_document()` and deliver answers with
`send_results()`. You build the real WhatsApp channel: a small Node bridge
using Baileys that owns the WhatsApp session and
forwards incoming files to our FastAPI webhook, plus the thin Python adapter
behind it. The full HTTP contract — both directions, exact payload shapes —
is already written in `src/wadr/adapters/openwa.py`; treat that docstring as
your spec.

**Files you own:** `bridge/` (new, Node), `src/wadr/adapters/openwa.py`,
the `/webhook/openwa` routes in `src/wadr/api/app.py`.

**Tasks (dependency order):**
- [x] Node bridge in `bridge/`: Baileys session; on document message, POST the base64 payload to `/webhook/openwa`
- [x] `OpenWAAdapter.handle_webhook()`: decode base64, parse ISO timestamp, call `on_document()`, return `{document_id, duplicate}`
- [x] Replace the 501 stub route in `api/app.py` with a real call into the adapter
- [x] `OpenWAAdapter.send_results()`: format results as a WhatsApp message, POST to bridge `/send`
- [x] Bridge forwards `/find <query>` chat messages → `/webhook/openwa/query` → search → reply in the same chat
- [x] Unskip the WS1 tests in `tests/test_todo_checklist.py`

**Definition of done:** sending a PDF to the linked WhatsApp number creates a
`documents` row; `/find <word>` in a chat gets a ranked reply; re-forwarding
the same file creates a sighting, not a new document; WS1 tests green.

**Syllabus module:** IR system architecture — document acquisition (the
"gathering" stage of the pipeline).

---

## WS2 — Extractors (DOCX, OCR, voice notes)

**Context.** The ingestion router already dispatches by file extension and
tolerates failing extractors (it logs a warning and skips the file). Today
only `.txt/.md/.pdf` produce text; your three extractors raise
`NotImplementedError`. Each one is a pure function `bytes -> str` — the moment
it returns text, chunking, embedding, and search work with zero further
changes anywhere.

**Files you own:** `src/wadr/ingestion/extractors/docx.py`, `image_ocr.py`,
`audio_asr.py`, plus the scanned-page fallback in `pdf.py`.

**Tasks (dependency order):**
- [x] `docx.py` with python-docx (add the dependency): paragraphs + table cells
- [x] `image_ocr.py` with pytesseract + Pillow; document the tesseract system install in README
- [x] `pdf.py` fallback: pages with an empty text layer are scans — render to image, route through `image_ocr`
- [x] `audio_asr.py` with Whisper (model "base") for `.ogg`/`.opus` voice notes; needs ffmpeg
- [x] Add one sample file per new type to `sample_docs/` so the demo covers them
- [x] Unskip the WS2 tests

**Definition of done:** `uv run wadr ingest ./sample_docs` extracts text from
a docx, a photographed page, and a voice note; searching a word that exists
only in the voice note finds it; WS2 tests green.

**Syllabus module:** document preprocessing — text extraction, tokenization
pipeline, handling heterogeneous formats.

---

## WS3 — Evaluation (judgments + hand-written metrics + benchmark)

**Context.** The report needs a measured comparison of all retrieval models,
and the viva needs proof we can compute IR metrics by hand. You build the
gold data (queries with graded relevance judgments over the shared corpus),
implement the metrics from the lecture formulas — **no libraries, that is the
point** — and produce the benchmark table.

**Files you own:** `src/wadr/evaluation/metrics.py`, `judgments.py`,
`run_eval.py`, and a new `evaluation/queries.jsonl` (format documented in
`judgments.py`).

**Tasks (dependency order):**
- [~] ~40 queries in `queries.jsonl` over the shared test corpus; include phrase
      queries and filter-style queries. **24 written** in `evaluation/queries.jsonl`,
      graded by one person from the document text — review the grades and extend
      to ~40. q19-q24 are filter-style; all five models honour filters now.
- [x] Grade relevance 0–3 per (query, document), keyed by `file_hash` so judgments survive re-ingest
- [x] `metrics.py`: P@k, R@k, F1@k, reciprocal rank, nDCG@k — pure Python, formula comments
- [x] `judgments.py` loader with validation (unique qids, grades in 1..3)
- [x] `run_eval.py`: every model × every query, macro-average, print the markdown table
- [x] Unskip the WS3 tests (they encode worked examples — your implementations must reproduce them)

**Definition of done:** `uv run python -m wadr.evaluation.run_eval` prints the
model × metric table; that table goes in the report; WS3 tests green.

**Syllabus module:** IR evaluation — relevance judgments, precision/recall,
MRR, nDCG.

---

## WS4 — Query experience (filters, recency, similar, feedback)

**Context.** Retrieval works but is bare: no way to narrow by sender/chat/
date/type, no recency signal, no feedback loop. You make search feel like a
product. The DB schema for `standing_queries` and `feedback` already exists;
`filters.parse()` and `fusion.recency_boost()` have specified signatures
waiting for bodies.

**Files you own:** `src/wadr/retrieval/filters.py`, `recency_boost` in
`fusion.py`, the `/similar` and `/feedback` routes in `api/app.py`, the
standing-query hook in `ingestion/router.py` (marked TODO(WS4)).

**Tasks (dependency order):**
- [x] `filters.parse()`: strip `from:/in:/before:/after:/type:` tokens (docstring has the worked example)
- [x] Thread `Filters` into `service.search()` and the bm25/dense SQL (join `sightings`, WHERE clauses)
- [x] `fusion.recency_boost()`: decay on newest sighting age; wired into `_hybrid`.
      **w = 0.15, half-life = 30 days.** RRF scores are flat — rank 1 beats
      rank 10 by only 1.15x and rank 30 by 1.48x — so 0.15 lifts a same-day
      re-share about ten places; 0.5 overruled relevance entirely.
- [x] `/similar/{document_id}`: pgvector neighbors of the doc's chunks, excluding itself
- [x] `/feedback`: insert into the `feedback` table
- [x] Standing queries: after ingest, match the new doc against `standing_queries` and push via the adapter (CLI print is fine until WS1 lands)
- [x] Unskip the WS4 tests

**Definition of done:** `wadr search "notes from:cli after:2026-01-01 type:pdf"`
filters correctly; re-sharing a document today visibly lifts its hybrid rank;
`/similar` returns sensible neighbors; WS4 tests green.

**Syllabus module:** query languages & query processing; relevance feedback.

---

## SHARED — classical IR models (viva-critical, from scratch ONLY)

**Context.** These files are the course-lab evidence that we can build the
classical machinery by hand. **HARD RULE: no sklearn, no rank_bm25, no gensim
— dicts/sets/lists only (numpy allowed in tfidf only).** Expect the viva to go
through them line by line; comment accordingly. Pair-program these — every
member must be able to explain all three.

**Files:** `src/wadr/indexing/inverted_index.py`,
`src/wadr/retrieval/boolean_model.py`, `src/wadr/retrieval/tfidf_model.py`.

- [x] `inverted_index.py`: ~100 readable lines, dict term → sorted posting list, AND/OR/NOT (spec in the module docstring)
- [x] `boolean_model.py`: build the index from `documents.extracted_text`, evaluate the expression, wrap as `SearchResult`
- [x] `tfidf_model.py`: log-tf × idf, L2 normalize, cosine — numpy only, formula comments
- [x] Unskip the SHARED tests; `wadr search "cats AND dogs" --model boolean` works

**Syllabus modules:** Boolean model & inverted index construction; vector
space model (TF-IDF, cosine similarity).
