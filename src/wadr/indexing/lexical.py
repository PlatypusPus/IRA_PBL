"""Chunk persistence: text + tsvector (+ embedding when available) into Postgres."""

import psycopg

from wadr.db import to_vector


def index_chunks(
    conn: psycopg.Connection,
    document_id: int,
    texts: list[str],
    embeddings: list[list[float]] | None,
) -> None:
    """Upsert chunk rows. tsv is computed in-database; embedding may be NULL
    (Ollama down - dense search simply won't see these chunks)."""
    for i, text in enumerate(texts):
        emb = to_vector(embeddings[i]) if embeddings else None
        conn.execute(
            """
            INSERT INTO chunks (document_id, chunk_index, text, embedding, tsv)
            VALUES (%s, %s, %s, %s::vector, to_tsvector('english', %s))
            ON CONFLICT (document_id, chunk_index)
            DO UPDATE SET text = EXCLUDED.text, embedding = EXCLUDED.embedding,
                          tsv = EXCLUDED.tsv
            """,
            (document_id, i, text, emb, text),
        )
