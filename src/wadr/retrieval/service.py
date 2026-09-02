"""Search entry point.

Ranking is BM25 (rank_bm25) fused with dense embeddings (nomic-embed-text via
Ollama) by Reciprocal Rank Fusion, then nudged by recency. Both are mature,
pretrained components - this product has no business reimplementing retrieval
models. Hybrid is the default and the only one the UI exposes; bm25 and dense
stay reachable for debugging and for when Ollama is not running.

Every search is scoped to the caller's own linked WhatsApp numbers. That is
enforced here, in one place, rather than trusted to callers.
"""

import logging
from dataclasses import replace

import psycopg

from wadr.accounts import account_ids
from wadr.db import get_conn
from wadr.models import SearchResult
from wadr.retrieval import bm25_model, dense_model, filters, fusion

log = logging.getLogger(__name__)

MODELS = ("hybrid", "bm25", "dense")

# Dense retrieval has no notion of "no answer" - it always returns the nearest
# k vectors, however far away. Measured on this embedder, real matches and pure
# noise OVERLAP: "carbon emissions" correctly finds a kWh table at 0.438 while
# "quantum chromodynamics" hits an unrelated document at 0.454. So a score
# floor cannot separate them without throwing away real answers. Instead we
# keep the result and mark it weak, and the UI says "closest I found" rather
# than claiming a match. Above this, a semantic-only hit is trustworthy.
DENSE_CONFIDENT = 0.55
CANDIDATES = 30  # chunk-level pool retrieved before collapsing to one hit per document


def search(
    query: str, user_id: int, model: str = "hybrid", top_k: int = 5
) -> list[SearchResult]:
    """Search the documents this user's numbers have received."""
    query, f = filters.parse(query)  # strips from:/in:/before:/after:/type:
    with get_conn() as conn:
        f = replace(f, account_ids=account_ids(conn, user_id))
        if not f.account_ids:
            return []  # no numbers linked yet: nothing of yours to search
        if model == "bm25":
            hits = bm25_model.search(conn, query, CANDIDATES, f)
        elif model == "dense":
            hits = dense_model.search(conn, query, CANDIDATES, f)
        elif model == "hybrid":
            hits = _hybrid(conn, query, CANDIDATES, f)
        else:
            raise ValueError(f"unknown model: {model}")
        results = _one_per_document(hits)[:top_k]
        _enrich(conn, query, results)
        return results


def similar(document_id: int, user_id: int, top_k: int = 5) -> list[SearchResult]:
    """More-like-this: nearest neighbours of a document's chunks, itself excluded.

    Scoped both ways - you must be able to see the source document, and only
    documents you can see come back.
    """
    with get_conn() as conn:
        mine = account_ids(conn, user_id)
        if not mine:
            raise LookupError(f"no document {document_id}")
        visible = conn.execute(
            "SELECT 1 FROM sightings WHERE document_id = %s AND account_id = ANY(%s) LIMIT 1",
            (document_id, mine),
        ).fetchone()
        if visible is None:
            # Same error as "does not exist": whether a document you cannot see
            # exists is not your business.
            raise LookupError(f"no document {document_id}")
        rows = conn.execute(
            "SELECT * FROM ("
            "  SELECT DISTINCT ON (c2.document_id)"
            "         c2.id, c2.document_id, c2.text, d.filename,"
            "         1 - (c1.embedding <=> c2.embedding) AS score"
            "    FROM chunks c1"
            "    JOIN chunks c2 ON c2.document_id <> c1.document_id"
            "    JOIN documents d ON d.id = c2.document_id"
            "   WHERE c1.document_id = %s"
            "     AND c1.embedding IS NOT NULL AND c2.embedding IS NOT NULL"
            "     AND EXISTS (SELECT 1 FROM sightings s"
            "                  WHERE s.document_id = d.id AND s.account_id = ANY(%s))"
            "   ORDER BY c2.document_id, c1.embedding <=> c2.embedding"
            ") best ORDER BY score DESC LIMIT %s",
            (document_id, mine, top_k),
        ).fetchall()
        return [
            SearchResult(
                chunk_id=r[0], document_id=r[1], filename=r[3],
                snippet=r[2][:200], score=float(r[4]),
            )
            for r in rows
        ]


def get_document(document_id: int, user_id: int) -> tuple[str, str, bytes] | None:
    """(filename, mime_type, content) for download, or None if not yours."""
    with get_conn() as conn:
        mine = account_ids(conn, user_id)
        if not mine:
            return None
        row = conn.execute(
            "SELECT d.filename, d.mime_type, d.content FROM documents d"
            " WHERE d.id = %s AND EXISTS (SELECT 1 FROM sightings s"
            "   WHERE s.document_id = d.id AND s.account_id = ANY(%s))",
            (document_id, mine),
        ).fetchone()
    if row is None or row[2] is None:
        return None
    return row[0], row[1], bytes(row[2])


def _hybrid(
    conn: psycopg.Connection, query: str, limit: int, f: filters.Filters
) -> list[SearchResult]:
    """BM25 + dense fused with RRF (k=60), then nudged by recency; degrades to
    BM25-only when the embedder is unavailable (dense returns [] and warns)."""
    lex = bm25_model.search(conn, query, CANDIDATES, f)
    den = dense_model.search(conn, query, CANDIDATES, f)
    if not den:
        return lex[:limit]
    by_chunk = {r.chunk_id: r for r in [*den, *lex]}
    lexical_hits = {r.chunk_id for r in lex}
    dense_score = {r.chunk_id: r.score for r in den}
    fused = fusion.rrf([[r.chunk_id for r in lex], [r.chunk_id for r in den]])
    # Recency applies to the whole candidate pool, before the cut - boosting
    # only the survivors could never pull a fresh doc into the top-k.
    latest = _latest_sightings(conn, [r.document_id for r in by_chunk.values()])
    fused = fusion.recency_boost(
        fused,
        {cid: latest[r.document_id] for cid, r in by_chunk.items() if r.document_id in latest},
    )
    return [
        replace(
            by_chunk[cid],
            score=score,
            # no keyword matched, and the vector was only loosely close
            weak=cid not in lexical_hits and dense_score.get(cid, 0.0) < DENSE_CONFIDENT,
        )
        for cid, score in fused[:limit]
    ]


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
    # keyword-in-context snippet, *bold* around matches; ts_headline falls back
    # to the start of the chunk when nothing matches.
    snippets = dict(
        conn.execute(
            "SELECT id, ts_headline('english', text,"
            "   websearch_to_tsquery('english', %s),"
            "   'StartSel=*,StopSel=*,MaxWords=35,MinWords=15,MaxFragments=1')"
            " FROM chunks WHERE id = ANY(%s)",
            (query, chunk_ids),
        ).fetchall()
    )
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
