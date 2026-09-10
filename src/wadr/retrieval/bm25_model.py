"""BM25 lexical retrieval via rank_bm25 over chunk texts.

ponytail: loads the whole chunk corpus per query - fine at course scale.
Past ~10k chunks, prefilter candidates with the tsv GIN index
(WHERE tsv @@ websearch_to_tsquery('english', %s)) before scoring.
"""

import re

import psycopg
from rank_bm25 import BM25Okapi

from wadr.models import SearchResult
from wadr.retrieval.filters import Filters, where

# Ordinals and Roman numerals are the same thing as digits, and the two sides of
# a search rarely agree on which to use: a college notice OCRs as "I and II Year
# B.E." while the person looking for it types "1st and 2nd year". Both the query
# and the documents go through this, so it matches in either direction.
#
# Bare "i", "v" and "x" are deliberately missing. "i" is the English pronoun -
# it appears as a standalone token in 12 of the 44 documents measured here, so
# mapping it to "1" would make a search for "1" hit a quarter of the corpus.
# Multi-letter numerals have no such collision.
_WORD_NUMBER = {
    "first": "1", "second": "2", "third": "3", "fourth": "4",
    "fifth": "5", "sixth": "6", "seventh": "7", "eighth": "8",
    "ii": "2", "iii": "3", "iv": "4", "vi": "6", "vii": "7", "viii": "8", "ix": "9",
}
_ORDINAL = re.compile(r"^(\d+)(?:st|nd|rd|th)$")  # 1st -> 1, 22nd -> 22


def _normalize(token: str) -> str:
    if token in _WORD_NUMBER:
        return _WORD_NUMBER[token]
    digits = _ORDINAL.match(token)
    return digits.group(1) if digits else token


def _tokenize(text: str) -> list[str]:
    return [_normalize(t) for t in re.findall(r"\w+", text.lower())]


def search(
    conn: psycopg.Connection, query: str, top_k: int = 5, filters: Filters | None = None
) -> list[SearchResult]:
    predicate, params = where(filters)
    rows = conn.execute(
        "SELECT c.id, c.document_id, c.text, d.filename"
        " FROM chunks c JOIN documents d ON d.id = c.document_id"
        f" WHERE true{predicate}",
        params,
    ).fetchall()
    if not rows:
        return []
    corpus = [_tokenize(r[2]) for r in rows]
    terms = _tokenize(query)
    scores = BM25Okapi(corpus).get_scores(terms)

    # Whether a chunk matches is decided by the words in it, NOT by the sign of
    # its BM25 score. On a small corpus - one user with a handful of documents -
    # a term present in every document gets a NEGATIVE idf, so "payslip" across
    # three payslips scores -0.359 for all three and a `score > 0` filter throws
    # away every correct answer. BM25 is only asked to order the matches.
    wanted = set(terms)
    hits = [
        (row, score)
        for row, score, tokens in zip(rows, scores, corpus, strict=True)
        if wanted & set(tokens)
    ]
    hits.sort(key=lambda pair: -pair[1])
    return [
        SearchResult(
            chunk_id=r[0], document_id=r[1], filename=r[3], snippet=r[2][:200], score=float(s)
        )
        for r, s in hits[:top_k]
    ]
