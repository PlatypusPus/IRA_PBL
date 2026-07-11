"""From-scratch inverted index - COURSE LAB EVIDENCE, viva-critical.

TODO(SHARED): implement exactly as specified here. HARD RULE: no libraries -
plain dicts, sets and lists only (re is fine, it's stdlib). This file is our
proof that we can build the classical data structure by hand; target ~100
readable, commented lines. Do NOT swap in rank_bm25, sklearn, whoosh, or
Postgres full-text search.

Spec
----
- tokenize(text): lowercase, split on non-alphanumerics.
- InvertedIndex._index: dict term -> sorted, deduplicated list of doc_ids
  (the posting list).
- add_document(doc_id, text): update the posting lists.
- query(expr): Boolean retrieval with AND / OR / NOT, evaluated left to right
  (no precedence or parentheses required), where AND = intersection,
  OR = union, NOT = difference with the next term's postings.
- vocabulary() and posting_list(term) helpers for demo screenshots.

Used by retrieval/boolean_model.py, populated from documents.extracted_text.
"""


class InvertedIndex:
    def __init__(self) -> None:
        raise NotImplementedError("TODO(SHARED): from-scratch inverted index")

    def add_document(self, doc_id: int, text: str) -> None:
        """Tokenize and add doc_id to every term's posting list."""
        raise NotImplementedError("TODO(SHARED): from-scratch inverted index")

    def query(self, expr: str) -> set[int]:
        """Boolean AND/OR/NOT retrieval over posting lists, left to right.

        e.g. query("cats AND dogs NOT birds") -> set of matching doc_ids.
        """
        raise NotImplementedError("TODO(SHARED): from-scratch inverted index")
