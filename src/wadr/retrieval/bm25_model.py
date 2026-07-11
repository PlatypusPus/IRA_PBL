"""BM25 lexical retrieval via rank_bm25 over chunk texts.

ponytail: loads the whole chunk corpus per query - fine at course scale.
Past ~10k chunks, prefilter candidates with the tsv GIN index
(WHERE tsv @@ websearch_to_tsquery('english', %s)) before scoring.
"""

import re

import psycopg
from rank_bm25 import BM25Okapi

from wadr.models import SearchResult


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def search(conn: psycopg.Connection, query: str, top_k: int = 5) -> list[SearchResult]:
    rows = conn.execute(
        "SELECT c.id, c.document_id, c.text, d.filename"
        " FROM chunks c JOIN documents d ON d.id = c.document_id"
    ).fetchall()
    if not rows:
        return []
    bm25 = BM25Okapi([_tokenize(r[2]) for r in rows])
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(zip(rows, scores, strict=True), key=lambda pair: -pair[1])[:top_k]
    return [
        SearchResult(
            chunk_id=r[0], document_id=r[1], filename=r[3], snippet=r[2][:200], score=float(s)
        )
        for r, s in ranked
        if s > 0
    ]
