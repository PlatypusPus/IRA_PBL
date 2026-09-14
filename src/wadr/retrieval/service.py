"""Model dispatch + hybrid orchestration - the one search entry point for CLI and API."""

import logging
from dataclasses import replace

import psycopg

from wadr.db import get_conn
from wadr.models import SearchResult
from wadr.retrieval import bm25_model, boolean_model, dense_model, filters, fusion, tfidf_model

log = logging.getLogger(__name__)

CANDIDATES = 30  # chunk-level pool retrieved before collapsing to one hit per document


def search(query: str, model: str = "hybrid", top_k: int = 5) -> list[SearchResult]:
    query, f = filters.parse(query)  # strips from:/in:/before:/after:/type:
    if not query.strip():
        return []
    with get_conn() as conn:
        if model == "boolean":
            return boolean_model.search(conn, query, top_k, f)
        if model == "bm25":
            hits = bm25_model.search(conn, query, CANDIDATES, f)
        elif model == "tfidf":
            # chunk-level like bm25/dense, so it takes the same path: collapse to
            # one hit per document and enrich. Boolean stays separate above - it
            # is document-level and unranked, with no chunk to point at.
            hits = tfidf_model.search(conn, query, CANDIDATES, f)
        elif model == "dense":
            hits = dense_model.search(conn, query, CANDIDATES, f)
        elif model == "hybrid":
            hits = _hybrid(conn, query, CANDIDATES, f)
        else:
            raise ValueError(f"unknown model: {model}")
        # One hit per document (the top chunk), then enrich for display.
        results = _one_per_document(hits)[:top_k]
        _enrich(conn, query, results)
        return results


def _hybrid(
    conn: psycopg.Connection, query: str, limit: int, f: filters.Filters | None = None
) -> list[SearchResult]:
    """BM25 + dense fused with RRF (k=60), then nudged by recency; degrades to
    BM25-only when the embedder is unavailable (dense returns [] and warns)."""
    lex = bm25_model.search(conn, query, CANDIDATES, f)
    den = dense_model.search(conn, query, CANDIDATES, f)
    if not den:
        return lex[:limit]
    by_chunk = {r.chunk_id: r for r in [*den, *lex]}
    fused = fusion.rrf([[r.chunk_id for r in lex], [r.chunk_id for r in den]])
    # Recency applies to the whole candidate pool, before the cut - boosting
    # only the survivors could never pull a fresh doc into the top-k.
    latest = _latest_sightings(conn, [r.document_id for r in by_chunk.values()])
    fused = fusion.recency_boost(
        fused,
        {cid: latest[r.document_id] for cid, r in by_chunk.items() if r.document_id in latest},
    )
    return [replace(by_chunk[cid], score=score) for cid, score in fused[:limit]]


def _latest_sightings(conn: psycopg.Connection, doc_ids: list[int]) -> dict:
    """document_id -> newest sent_at, for the recency boost."""
    return dict(
        conn.execute(
            "SELECT document_id, max(sent_at) FROM sightings"
            " WHERE document_id = ANY(%s) GROUP BY document_id",
            (doc_ids,),
        ).fetchall()
    )


def _one_per_document(hits: list[SearchResult]) -> list[SearchResult]:
    """Collapse chunk hits to one per document, keeping the best-scoring chunk.
    `hits` is already score-ordered, so first-seen per document wins."""
    seen: set[int] = set()
    out: list[SearchResult] = []
    for r in hits:
        if r.document_id not in seen:
            seen.add(r.document_id)
            out.append(r)
    return out


def _enrich(conn: psycopg.Connection, query: str, results: list[SearchResult]) -> None:
    """Attach a keyword-in-context snippet and provenance (who shared it, when)
    to the final results. One query each; mutates the results in place."""
    if not results:
        return
    chunk_ids = [r.chunk_id for r in results]
    doc_ids = [r.document_id for r in results]
    # keyword-in-context snippet, *bold* around matches (renders bold in WhatsApp);
    # ts_headline falls back to the start of the chunk when nothing matches.
    snippets = dict(
        conn.execute(
            "SELECT id, ts_headline('english', text,"
            "   websearch_to_tsquery('english', %s),"
            "   'StartSel=*,StopSel=*,MaxWords=35,MinWords=15,MaxFragments=1')"
            " FROM chunks WHERE id = ANY(%s)",
            (query, chunk_ids),
        ).fetchall()
    )
    # newest sighting per document: who shared it and when
    sightings = {
        row[0]: (row[1], row[2])
        for row in conn.execute(
            "SELECT DISTINCT ON (document_id) document_id, sender, sent_at"
            " FROM sightings WHERE document_id = ANY(%s)"
            " ORDER BY document_id, sent_at DESC",
            (doc_ids,),
        ).fetchall()
    }
    for r in results:
        r.snippet = snippets.get(r.chunk_id, r.snippet).strip()
        r.sender, r.sent_at = sightings.get(r.document_id, (None, None))


# Matches the `action` values the feedback table was designed for; anything else
# is a client bug and is rejected rather than silently logged as noise.
FEEDBACK_ACTIONS = ("opened", "thumbs_up", "thumbs_down")


def similar(document_id: int, top_k: int = 5) -> list[SearchResult]:
    """Documents whose chunks sit closest to this document's chunks in the
    embedding space - "more like this", the query being a document.

    Raises LookupError if the document does not exist. Returns [] when nothing
    is embedded (Ollama was down at ingest time), same as dense search.

    ponytail: an all-pairs chunk comparison, which is O(chunks_in_doc x corpus).
    Fine for a course corpus; past ~10k chunks give `chunks` an HNSW index and
    compare against the document's mean vector instead.
    """
    with get_conn() as conn:
        if conn.execute(
            "SELECT 1 FROM documents WHERE id = %s", (document_id,)
        ).fetchone() is None:
            raise LookupError(f"no document {document_id}")
        rows = conn.execute(
            # DISTINCT ON keeps the single closest chunk per neighbouring
            # document, then the outer query re-sorts those by similarity.
            "SELECT * FROM ("
            "  SELECT DISTINCT ON (c2.document_id)"
            "         c2.id, c2.document_id, c2.text, d.filename,"
            "         1 - (c1.embedding <=> c2.embedding) AS score"
            "    FROM chunks c1"
            "    JOIN chunks c2 ON c2.document_id <> c1.document_id"
            "    JOIN documents d ON d.id = c2.document_id"
            "   WHERE c1.document_id = %s"
            "     AND c1.embedding IS NOT NULL AND c2.embedding IS NOT NULL"
            "   ORDER BY c2.document_id, c1.embedding <=> c2.embedding"
            ") best ORDER BY score DESC LIMIT %s",
            (document_id, top_k),
        ).fetchall()
        return [
            SearchResult(
                chunk_id=r[0], document_id=r[1], filename=r[3],
                snippet=r[2][:200], score=float(r[4]),
            )
            for r in rows
        ]


def log_feedback(query_text: str, document_id: int, action: str) -> int:
    """Record a relevance signal; returns the new feedback row id.

    Raises ValueError for an unknown action or an unknown document - this is a
    trust boundary, the payload comes straight off an HTTP request.
    """
    if action not in FEEDBACK_ACTIONS:
        raise ValueError(f"action must be one of {FEEDBACK_ACTIONS}, got {action!r}")
    if not query_text or not query_text.strip():
        raise ValueError("query_text must not be empty")
    with get_conn() as conn:
        if conn.execute(
            "SELECT 1 FROM documents WHERE id = %s", (document_id,)
        ).fetchone() is None:
            raise ValueError(f"no document {document_id}")
        return conn.execute(
            "INSERT INTO feedback (query_text, document_id, action)"
            " VALUES (%s, %s, %s) RETURNING id",
            (query_text, document_id, action),
        ).fetchone()[0]
