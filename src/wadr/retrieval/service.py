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
    query: str,
    user_id: int,
    model: str = "hybrid",
    top_k: int = 5,
    seen_by: tuple[str, str] | None = None,
) -> list[SearchResult]:
    """Search the documents this user's numbers have received.

    seen_by=(sender, chat) narrows that to what one other person could already
    see - set it when the search was typed by a group member rather than by the
    account owner. None is the owner, who sees all of their own documents.
    """
    query, f = filters.parse(query)  # strips from:/in:/before:/after:/type:
    with get_conn() as conn:
        f = replace(f, account_ids=account_ids(conn, user_id), seen_by=seen_by)
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
        _enrich(conn, query, results, f)
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


def get_document(
    document_id: int, user_id: int, seen_by: tuple[str, str] | None = None
) -> tuple[str, str, bytes] | None:
    """(filename, mime_type, content) for download, or None if not yours.

    seen_by narrows it the same way search() does, so a group member cannot
    /get a file they were never allowed to find.
    """
    with get_conn() as conn:
        mine = account_ids(conn, user_id)
        if not mine:
            return None
        seen_sql, seen_params = filters.seen_by_sql(seen_by)
        row = conn.execute(
            "SELECT d.filename, d.mime_type, d.content FROM documents d"
            " WHERE d.id = %s AND EXISTS (SELECT 1 FROM sightings s"
            f"   WHERE s.document_id = d.id AND s.account_id = ANY(%s){seen_sql})",
            (document_id, mine, *seen_params),
        ).fetchone()
    if row is None or row[2] is None:
        return None
    return row[0], row[1], bytes(row[2])


def get_document_text(document_id: int, user_id: int, max_chars: int = 20_000) -> dict | None:
    """Extracted text of a document, for an agent to actually read.

    Truncated: a 200-page scan would otherwise blow an agent's context in one
    tool call. The reply says when it was cut so the caller knows.
    """
    with get_conn() as conn:
        mine = account_ids(conn, user_id)
        if not mine:
            return None
        row = conn.execute(
            "SELECT d.id, d.filename, d.mime_type, d.extracted_text FROM documents d"
            " WHERE d.id = %s AND EXISTS (SELECT 1 FROM sightings s"
            "   WHERE s.document_id = d.id AND s.account_id = ANY(%s))",
            (document_id, mine),
        ).fetchone()
    if row is None:
        return None
    text = row[3] or ""
    return {
        "document_id": row[0],
        "filename": row[1],
        "mime_type": row[2],
        "text": text[:max_chars],
        "truncated": len(text) > max_chars,
        "total_characters": len(text),
    }


def recent_documents(user_id: int, limit: int = 20) -> list[dict]:
    """Most recently received documents - what an agent should look at when
    asked "what did I get this week"."""
    with get_conn() as conn:
        mine = account_ids(conn, user_id)
        if not mine:
            return []
        rows = conn.execute(
            "SELECT d.id, d.filename, d.mime_type, max(s.sent_at), min(s.sender)"
            "  FROM documents d JOIN sightings s ON s.document_id = d.id"
            " WHERE s.account_id = ANY(%s)"
            " GROUP BY d.id, d.filename, d.mime_type"
            " ORDER BY max(s.sent_at) DESC LIMIT %s",
            (mine, limit),
        ).fetchall()
    return [
        {
            "document_id": r[0], "filename": r[1], "mime_type": r[2],
            "received_at": r[3].isoformat() if r[3] else None, "sender": r[4],
        }
        for r in rows
    ]


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


def _enrich(
    conn: psycopg.Connection, query: str, results: list[SearchResult], f: filters.Filters
) -> None:
    """Attach a keyword-in-context snippet, provenance (who shared it, when) and
    mime type to the final results. One query each; mutates them in place."""
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
    # Scoped exactly like the search was: the newest sighting of a shared file
    # may belong to a different tenant, and "from <their contact>" is their
    # business, not the searcher's.
    seen_sql, seen_params = filters.seen_by_sql(f.seen_by)
    sightings = {
        row[0]: (row[1], row[2], row[3])
        for row in conn.execute(
            "SELECT DISTINCT ON (s.document_id) s.document_id, s.sender, s.sent_at, d.mime_type"
            "  FROM sightings s JOIN documents d ON d.id = s.document_id"
            f" WHERE s.document_id = ANY(%s) AND s.account_id = ANY(%s){seen_sql}"
            " ORDER BY s.document_id, s.sent_at DESC",
            (doc_ids, f.account_ids, *seen_params),
        ).fetchall()
    }
    for r in results:
        r.snippet = snippets.get(r.chunk_id, r.snippet).strip()
        r.sender, r.sent_at, r.mime_type = sightings.get(r.document_id, (None, None, None))
