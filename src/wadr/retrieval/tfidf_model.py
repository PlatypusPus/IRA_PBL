"""TF-IDF vector space model, from scratch - viva evidence.

HARD RULE: numpy only, no sklearn/gensim. The three formulas, applied to
chunk texts (same unit BM25 and the dense model rank, so the benchmark
compares like with like):

    tf(t, d)  = 1 + log10(count(t, d))     log-normalized term frequency:
                                           the 50th occurrence of a word says
                                           far less than the 2nd
    idf(t)    = log10(N / df(t))           rare terms discriminate; a term in
                                           every document scores log10(1) = 0
    weight    = tf * idf, then each document vector L2-normalized so that a
                long document cannot win on length alone
    score     = cosine(q, d) = q . d       (a plain dot product once both
                                           vectors are unit length)

ponytail: rebuilds the whole term-document matrix per query, and builds it
dense. Fine at course scale; past ~10k chunks hold the matrix in a sparse
structure (or cache it and invalidate on ingest) instead.
"""

from collections import Counter

import numpy as np
import psycopg

from wadr.indexing.inverted_index import tokenize  # shared tokenizer, see its docstring
from wadr.models import SearchResult
from wadr.retrieval.filters import Filters, where


def search(
    conn: psycopg.Connection, query: str, top_k: int = 5, filters: Filters | None = None
) -> list[SearchResult]:
    """Rank chunks by cosine similarity in the TF-IDF vector space.

    Note for the report: filtering shrinks the corpus, so N and df change and
    the idf weights are computed over the filtered set. Scores are therefore
    comparable within one filter, not across different ones - the same caveat
    BM25 carries.
    """
    predicate, params = where(filters)
    rows = conn.execute(
        "SELECT c.id, c.document_id, c.text, d.filename"
        " FROM chunks c JOIN documents d ON d.id = c.document_id"
        f" WHERE true{predicate}",
        params,
    ).fetchall()
    if not rows:
        return []

    documents = [tokenize(r[2]) for r in rows]
    n_docs = len(documents)

    # ---- vocabulary: every distinct term, in a fixed order = the axes
    vocabulary = {term: i for i, term in enumerate(sorted({t for d in documents for t in d}))}
    if not vocabulary:
        return []

    # ---- df(t): how many documents contain t at least once
    doc_frequency = np.zeros(len(vocabulary))
    for terms in documents:
        for term in set(terms):
            doc_frequency[vocabulary[term]] += 1
    idf = np.log10(n_docs / doc_frequency)  # df >= 1 for every term in the vocabulary

    # ---- the term-document matrix, one row per chunk
    matrix = np.zeros((n_docs, len(vocabulary)))
    for row, terms in enumerate(documents):
        for term, count in Counter(terms).items():
            matrix[row, vocabulary[term]] = 1 + np.log10(count)
    matrix *= idf

    # ---- L2-normalize every document vector, so cosine is just a dot product
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1  # an all-stopword chunk has no direction; leave it at zero
    matrix /= norms

    # ---- the query becomes a vector in the same space
    query_vector = np.zeros(len(vocabulary))
    for term, count in Counter(tokenize(query)).items():
        if term in vocabulary:  # a term nobody indexed cannot discriminate
            query_vector[vocabulary[term]] = (1 + np.log10(count)) * idf[vocabulary[term]]
    query_norm = np.linalg.norm(query_vector)
    if query_norm == 0:
        return []  # no query term appears anywhere in the corpus
    query_vector /= query_norm

    scores = matrix @ query_vector  # cosine, both sides being unit vectors
    ranked = np.argsort(-scores)[:top_k]
    return [
        SearchResult(
            chunk_id=rows[i][0],
            document_id=rows[i][1],
            filename=rows[i][3],
            snippet=rows[i][2][:200],
            score=float(scores[i]),
        )
        for i in ranked
        if scores[i] > 0
    ]
