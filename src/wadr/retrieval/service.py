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
    with get_conn() as conn:
        if model == "boolean":
            return boolean_model.search(conn, query, top_k)  # TODO(SHARED)
        if model == "tfidf":
            return tfidf_model.search(conn, query, top_k)  # TODO(SHARED)
        if model == "bm25":
            hits = bm25_model.search(conn, query, CANDIDATES, f)
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
        fused, {cid: latest[r.document_id] for cid, r in by_chunk.items() if r.document_id in latest}
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
