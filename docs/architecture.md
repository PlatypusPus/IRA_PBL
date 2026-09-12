# Architecture

```
 WhatsApp chats            ./sample_docs (or any folder)
      |                          |
      v                          v
+------------------+    +----------------+
| WhatsApp bridge  |    |                |
| (Baileys, Node)  |    |   CLIAdapter   |          adapters/ -- THIN,
+--------+---------+    |   (working)    |          no IR logic inside
         | webhook      +-------+--------+
         v                      |
+------------------+            |
|  OpenWAAdapter   |            |
|  (working)       |            |
+--------+---------+            |
         |    on_document()     |
         v                      v
+---------------------------------------------------+
| ingestion/   router -> extractor -> dedupe(SHA256) |
|              -> chunker                            |
|              txt/md/pdf/docx/image-OCR/voice-ASR   |
+-------------------------+-------------------------+
                          v
+---------------------------------------------------+
| indexing/    embedder (Ollama, optional)           |     PostgreSQL 16
|              lexical (tsvector)              ----> |     + pgvector
|              inverted_index (from scratch)         |
+-------------------------+-------------------------+
                          v
+---------------------------------------------------+
| retrieval/   bm25 | dense | tfidf | boolean        |
|                   \     /                          |
|                RRF fusion (k=60)                   |
|              filters, recency boost                |
+-------------------------+-------------------------+
                          v
              results -> adapter.send_results()

| evaluation/  P@k Recall F1 MRR nDCG -- by hand      |
```

## Module map

| Package | Responsibility |
|---|---|
| `adapters/` | Channel glue only: CLI and the WhatsApp webhook. No IR logic. |
| `ingestion/` | Route a file to an extractor, dedupe by SHA-256, chunk the text. |
| `indexing/` | Embeddings (Ollama), Postgres tsvector, and the from scratch inverted index. |
| `retrieval/` | The ranking models, filter parsing, RRF fusion, the query service. |
| `evaluation/` | Relevance judgments and hand implemented metrics. |
| `api/` | FastAPI app: `/search`, `/similar/{id}`, `/feedback`, bridge webhooks. |

## Two hard rules

Enforced in review, details in [CONTRIBUTING.md](../CONTRIBUTING.md):

1. **The engine never imports adapters.** Dependency points inward only.
   Adapters call the engine, never the reverse.
2. **Classical IR modules stay library-free.** `inverted_index.py`,
   `boolean_model.py`, `tfidf_model.py` (numpy allowed there only) and
   `metrics.py` use the standard library and nothing else. These files are viva
   evidence that we built the classical machinery ourselves.
