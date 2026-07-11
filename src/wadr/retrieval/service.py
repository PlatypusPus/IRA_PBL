"""Model dispatch + hybrid orchestration - the one search entry point for CLI and API."""

import logging
from dataclasses import replace

import psycopg

from wadr.db import get_conn
from wadr.models import SearchResult
from wadr.retrieval import bm25_model, boolean_model, dense_model, fusion, tfidf_model

log = logging.getLogger(__name__)

CANDIDATES = 20  # per-model pool fed into RRF


def search(query: str, model: str = "hybrid", top_k: int = 5) -> list[SearchResult]:
    # TODO(WS4): filters.parse(query) here - strip from:/in:/before:/after:/type:
    # tokens and constrain the SQL in each model accordingly.
    with get_conn() as conn:
        if model == "bm25":
            return bm25_model.search(conn, query, top_k)
        if model == "dense":
            return dense_model.search(conn, query, top_k)
        if model == "boolean":
            return boolean_model.search(conn, query, top_k)  # TODO(SHARED)
        if model == "tfidf":
            return tfidf_model.search(conn, query, top_k)  # TODO(SHARED)
        if model == "hybrid":
            return _hybrid(conn, query, top_k)
        raise ValueError(f"unknown model: {model}")


def _hybrid(conn: psycopg.Connection, query: str, top_k: int) -> list[SearchResult]:
    """BM25 + dense fused with RRF (k=60); degrades to BM25-only when the
    embedder is unavailable (dense returns [] and warns)."""
    lex = bm25_model.search(conn, query, CANDIDATES)
    den = dense_model.search(conn, query, CANDIDATES)
    if not den:
        return lex[:top_k]
    by_chunk = {r.chunk_id: r for r in [*den, *lex]}
    fused = fusion.rrf([[r.chunk_id for r in lex], [r.chunk_id for r in den]])
    # TODO(WS4): fusion.recency_boost(fused, ...) before the cut.
    return [replace(by_chunk[cid], score=score) for cid, score in fused[:top_k]]
