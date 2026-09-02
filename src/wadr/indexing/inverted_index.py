"""From-scratch inverted index - COURSE LAB EVIDENCE, viva-critical.

HARD RULE: no libraries. Plain dicts, sets and lists (plus stdlib `re` for
tokenizing). No rank_bm25, no sklearn, no Postgres full-text search.

Structure
---------
    _index:  term -> posting list, a SORTED list of document ids
    _docs:   every document id ever added (needed for a leading NOT)

Why the posting lists are kept sorted: it lets AND / OR / NOT run as a single
linear merge of two lists (`_intersect` / `_union` / `_difference` below),
which is O(m + n) and touches each posting once. Converting to Python sets
would work too, but it would throw away the ordering that makes the classical
algorithm possible - and that algorithm is the point of this file.

Boolean queries are evaluated strictly LEFT TO RIGHT with no precedence and no
parentheses, exactly as the spec requires: "a AND b OR c" is "(a AND b) OR c".

Used by retrieval/boolean_model.py, populated from documents.extracted_text.
"""

import re

OPERATORS = ("AND", "OR", "NOT")


def tokenize(text: str) -> list[str]:
    """Lowercase, then split on every non-alphanumeric character.

    Deliberately identical to bm25_model._tokenize so that a benchmark
    comparing the models measures the *models*, not two tokenizers.
    """
    return re.findall(r"\w+", text.lower())


class InvertedIndex:
    def __init__(self) -> None:
        self._index: dict[str, list[int]] = {}
        self._docs: set[int] = set()

    # ------------------------------------------------------------- building

    def add_document(self, doc_id: int, text: str) -> None:
        """Tokenize and add doc_id to every term's posting list."""
        self._docs.add(doc_id)
        # set(): a term occurring 50 times in this document still yields one
        # posting. Term *frequency* is the vector-space model's job, not the
        # Boolean model's - here a term is simply present or absent.
        for term in set(tokenize(text)):
            postings = self._index.setdefault(term, [])
            if doc_id not in postings:
                # keep the list sorted by inserting at the right position
                position = 0
                while position < len(postings) and postings[position] < doc_id:
                    position += 1
                postings.insert(position, doc_id)

    # -------------------------------------------------------------- lookups

    def vocabulary(self) -> list[str]:
        """Every indexed term, alphabetically - for demo screenshots."""
        return sorted(self._index)

    def posting_list(self, term: str) -> list[int]:
        """Documents containing `term`, ascending. Unknown term -> []."""
        return self._index.get(term.lower(), [])

    # ------------------------------------------- set operations, by hand

    @staticmethod
    def _intersect(a: list[int], b: list[int]) -> list[int]:
        """AND: walk both sorted lists once, keeping ids present in both."""
        out: list[int] = []
        i = j = 0
        while i < len(a) and j < len(b):
            if a[i] == b[j]:
                out.append(a[i])
                i += 1
                j += 1
            elif a[i] < b[j]:
                i += 1          # a[i] can never appear later in b
            else:
                j += 1
        return out

    @staticmethod
    def _union(a: list[int], b: list[int]) -> list[int]:
        """OR: merge both sorted lists, emitting a shared id only once."""
        out: list[int] = []
        i = j = 0
        while i < len(a) or j < len(b):
            if j >= len(b) or (i < len(a) and a[i] < b[j]):
                out.append(a[i])
                i += 1
            elif i >= len(a) or b[j] < a[i]:
                out.append(b[j])
                j += 1
            else:                # equal: take it once, advance both
                out.append(a[i])
                i += 1
                j += 1
        return out

    @staticmethod
    def _difference(a: list[int], b: list[int]) -> list[int]:
        """NOT: walk both, keeping ids in `a` that are absent from `b`."""
        out: list[int] = []
        i = j = 0
        while i < len(a):
            if j >= len(b) or a[i] < b[j]:
                out.append(a[i])
                i += 1
            elif a[i] == b[j]:
                i += 1          # present in b -> excluded
                j += 1
            else:
                j += 1
        return out

    # ---------------------------------------------------------- evaluation

    def query(self, expr: str) -> set[int]:
        """Evaluate a Boolean expression, left to right, returning doc ids.

            query("cats AND dogs")   -> docs with both
            query("cats OR dogs")    -> docs with either
            query("cats NOT birds")  -> docs with cats but not birds

        Operators must be UPPERCASE, which is what lets "cats and dogs" search
        for the literal word "and" rather than being read as an operator.
        """
        result: list[int] | None = None
        operator = "AND"  # the operator waiting for its right-hand term
        for token in expr.split():
            if token in OPERATORS:
                operator = token
                continue
            # Run the token through the SAME tokenizer that built the index:
            # documents stored "tf-idf" as the two terms tf and idf, so looking
            # up the raw token would silently match nothing. A token that splits
            # into several terms requires all of them, which is how the indexer
            # stored them in the first place.
            terms = tokenize(token)
            if not terms:
                continue  # punctuation-only token, e.g. "--"
            postings = self.posting_list(terms[0])
            for extra in terms[1:]:
                postings = self._intersect(postings, self.posting_list(extra))
            if result is None:
                # The first term seeds the result. A leading NOT is the one
                # case needing the full document set to subtract from.
                result = (
                    self._difference(sorted(self._docs), postings)
                    if operator == "NOT"
                    else postings
                )
            elif operator == "AND":
                result = self._intersect(result, postings)
            elif operator == "OR":
                result = self._union(result, postings)
            else:
                result = self._difference(result, postings)
            operator = "AND"  # two adjacent terms with no operator mean AND
        return set(result or [])
