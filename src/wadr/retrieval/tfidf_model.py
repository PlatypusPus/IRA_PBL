"""TF-IDF vector space model, from scratch. TODO(SHARED).

HARD RULE: numpy only - no sklearn/gensim. Viva evidence for the
vector-space-model lecture, so comment every step:

    tf  = 1 + log10(count)        (log-normalized term frequency)
    idf = log10(N / df)
    doc vectors L2-normalized; score = cosine(query_vec, doc_vec)

Build the vocabulary and document matrix from chunks.text. Rebuilding per
query is acceptable at course scale (note it with a ponytail comment).
"""

import psycopg

from wadr.models import SearchResult


def search(conn: psycopg.Connection, query: str, top_k: int = 5) -> list[SearchResult]:
    """Rank chunks by cosine similarity in the TF-IDF vector space."""
    raise NotImplementedError("TODO(SHARED): from-scratch TF-IDF model")
