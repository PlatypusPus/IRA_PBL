"""Boolean retrieval over the from-scratch inverted index. TODO(SHARED).

HARD RULE: no retrieval libraries. Implement indexing/inverted_index.py first,
feed it documents.extracted_text, evaluate the AND/OR/NOT expression, and wrap
matching documents as SearchResult (score=1.0 - Boolean retrieval is set-based,
not ranked). Viva evidence for the Boolean-model lecture.
"""

import psycopg

from wadr.models import SearchResult


def search(conn: psycopg.Connection, query: str, top_k: int = 5) -> list[SearchResult]:
    """e.g. search(conn, "invoice AND october NOT draft")."""
    raise NotImplementedError("TODO(SHARED): boolean model over inverted_index")
