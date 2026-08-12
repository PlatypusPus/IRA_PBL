"""Dense retrieval: cosine similarity over pgvector embeddings."""

import psycopg

from wadr.db import to_vector
from wadr.indexing import embedder
from wadr.models import SearchResult
from wadr.retrieval.filters import Filters, where


def search(
    conn: psycopg.Connection, query: str, top_k: int = 5, filters: Filters | None = None
) -> list[SearchResult]:
    """Embed the query and rank chunks by cosine similarity.

    Returns [] (embedder logs a warning) when Ollama is unreachable -
    callers degrade to BM25-only.
    """
    qvec = embedder.embed_query(query)
    if qvec is None:
        return []
    vec = to_vector(qvec)
    predicate, params = where(filters)
    rows = conn.execute(
        "SELECT c.id, c.document_id, c.text, d.filename,"
        "       1 - (c.embedding <=> %s::vector) AS score"
        " FROM chunks c JOIN documents d ON d.id = c.document_id"
        " WHERE c.embedding IS NOT NULL"
        f"{predicate}"
        " ORDER BY c.embedding <=> %s::vector"
        " LIMIT %s",
        (vec, *params, vec, top_k),
    ).fetchall()
    return [
        SearchResult(
            chunk_id=r[0], document_id=r[1], filename=r[3], snippet=r[2][:200], score=float(r[4])
        )
        for r in rows
    ]
