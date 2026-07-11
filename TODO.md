# WADR — Team Assignment Sheet

The foundation is done: `wadr ingest` / `wadr search` work end-to-end with
BM25 + dense retrieval fused by RRF (BM25-only if Ollama is down). Everything
below is yours. Every stub raises `NotImplementedError` and has a matching
**skipped test in `tests/test_todo_checklist.py`** — delete the skip marker as
you implement; when the file is green, the project is done.

Rules that bind everyone are in [CONTRIBUTING.md](CONTRIBUTING.md):
the engine never imports adapters, and classical IR modules stay library-free.

---

## WS1 — WhatsApp integration (open-wa bridge + adapter)

**Context.** WADR's engine does not know WhatsApp exists: adapters hand it raw
bytes through `MessagingInterface.on_document()` and deliver answers with
`send_results()`. You build the real WhatsApp channel: a small Node bridge
using open-wa (`wa-automate-nodejs`) that owns the WhatsApp session and
forwards incoming files to our FastAPI webhook, plus the thin Python adapter
behind it. The full HTTP contract — both directions, exact payload shapes —
is already written in `src/wadr/adapters/openwa.py`; treat that docstring as
your spec.

**Files you own:** `bridge/` (new, Node), `src/wadr/adapters/openwa.py`,
the `/webhook/openwa` routes in `src/wadr/api/app.py`.

**Tasks (dependency order):**
- [ ] Node bridge in `bridge/`: open-wa session; on document message, POST the base64 payload to `/webhook/openwa`
- [ ] `OpenWAAdapter.handle_webhook()`: decode base64, parse ISO timestamp, call `on_document()`, return `{document_id, duplicate}`
- [ ] Replace the 501 stub route in `api/app.py` with a real call into the adapter
- [ ] `OpenWAAdapter.send_results()`: format results as a WhatsApp message, POST to bridge `/send`
- [ ] Bridge forwards `/find <query>` chat messages → `/webhook/openwa/query` → search → reply in the same chat
- [ ] Unskip the WS1 tests in `tests/test_todo_checklist.py`

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
- [ ] `docx.py` with python-docx (add the dependency): paragraphs + table cells
- [ ] `image_ocr.py` with pytesseract + Pillow; document the tesseract system install in README
- [ ] `pdf.py` fallback: pages with an empty text layer are scans — render to image, route through `image_ocr`
- [ ] `audio_asr.py` with Whisper (model "base") for `.ogg`/`.opus` voice notes; needs ffmpeg
- [ ] Add one sample file per new type to `sample_docs/` so the demo covers them
- [ ] Unskip the WS2 tests

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
- [ ] ~40 queries in `queries.jsonl` over the shared test corpus; include phrase queries and filter-style queries
- [ ] Grade relevance 0–3 per (query, document), keyed by `file_hash` so judgments survive re-ingest
- [ ] `metrics.py`: P@k, R@k, F1@k, reciprocal rank, nDCG@k — pure Python, formula comments
- [ ] `judgments.py` loader with validation (unique qids, grades in 1..3)
- [ ] `run_eval.py`: every model × every query, macro-average, print the markdown table
- [ ] Unskip the WS3 tests (they encode worked examples — your implementations must reproduce them)

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
- [ ] `filters.parse()`: strip `from:/in:/before:/after:/type:` tokens (docstring has the worked example)
- [ ] Thread `Filters` into `service.search()` and the bm25/dense SQL (join `sightings`, WHERE clauses)
- [ ] `fusion.recency_boost()`: exponential decay on newest sighting age; wire into `_hybrid`
- [ ] `/similar/{document_id}`: pgvector neighbors of the doc's chunks, excluding itself
- [ ] `/feedback`: insert into the `feedback` table
- [ ] Standing queries: after ingest, match the new doc against `standing_queries` and push via the adapter (CLI print is fine until WS1 lands)
- [ ] Unskip the WS4 tests

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

- [ ] `inverted_index.py`: ~100 readable lines, dict term → sorted posting list, AND/OR/NOT (spec in the module docstring)
- [ ] `boolean_model.py`: build the index from `documents.extracted_text`, evaluate the expression, wrap as `SearchResult`
- [ ] `tfidf_model.py`: log-tf × idf, L2 normalize, cosine — numpy only, formula comments
- [ ] Unskip the SHARED tests; `wadr search "cats AND dogs" --model boolean` works

**Syllabus modules:** Boolean model & inverted index construction; vector
space model (TF-IDF, cosine similarity).
