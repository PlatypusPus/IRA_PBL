"""Boolean retrieval over the from-scratch inverted index - viva evidence.

HARD RULE: no retrieval libraries. The index is indexing/inverted_index.py,
built here from documents.extracted_text.

Boolean retrieval is SET-BASED, not ranked: a document either satisfies the
expression or it does not, so every hit scores 1.0. That is the model's
defining limitation and the reason BM25 and the vector space model exist -
worth saying out loud in the report.

ponytail: rebuilds the index on every query, exactly like bm25_model loads the
corpus on every query. Fine at course scale (tens of documents). Past a few
thousand, build it once at startup or persist the posting lists.
"""

import psycopg

from wadr.indexing.inverted_index import InvertedIndex
from wadr.models import SearchResult
from wadr.retrieval.filters import Filters, where


def search(
    conn: psycopg.Connection, query: str, top_k: int = 5, filters: Filters | None = None
) -> list[SearchResult]:
    """e.g. search(conn, "invoice AND october NOT draft")."""
    predicate, params = where(filters)
    rows = conn.execute(
        "SELECT d.id, d.filename, d.extracted_text FROM documents d"
        f" WHERE true{predicate}",
        params,
    ).fetchall()

    index = InvertedIndex()
    texts = {}
    for doc_id, filename, extracted in rows:
        index.add_document(doc_id, extracted or "")
        texts[doc_id] = (filename, extracted or "")

    # Unranked, so order by document id: stable and reproducible for the report.
    matches = sorted(index.query(query))[:top_k]
    return [
        SearchResult(
            # ponytail: Boolean retrieval is document-level - there is no
            # "best chunk" to point at, so chunk_id is a placeholder. Nothing
            # downstream reads it for this model (service.py returns these
            # results directly, without the chunk-based enrichment step).
            chunk_id=0,
            document_id=doc_id,
            filename=texts[doc_id][0],
            snippet=texts[doc_id][1][:200],
            score=1.0,
        )
        for doc_id in matches
    ]
