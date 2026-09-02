"""IR effectiveness metrics BY HAND - viva evidence for the evaluation lecture.

HARD RULE: no sklearn / pytrec_eval / scipy - plain Python (math.log2 allowed).

Conventions used by every function here:
    ranked:   ordered list of retrieved doc ids (best first)
    relevant: dict doc id -> graded relevance 0-3 (grade-0 docs simply omitted)
Binary metrics treat grade > 0 as relevant; only nDCG uses the grades.

A note the report should make: precision, recall and F1 are SET measures
computed on a prefix - they cannot tell "relevant doc at rank 1" from
"relevant doc at rank 5". MRR and nDCG are the rank-aware ones, which is
exactly why the lecture pairs them.
"""

from math import log2


def _is_relevant(doc_id, relevant: dict) -> bool:
    """Binary relevance: any positive grade counts."""
    return relevant.get(doc_id, 0) > 0


def precision_at_k(ranked: list, relevant: dict, k: int) -> float:
    """P@k = |relevant docs in top-k| / k

    Divided by k, not by how many were actually returned: a system that
    returns 1 correct result when asked for 5 has not earned P@5 = 1.0.
    """
    if k <= 0:
        return 0.0
    hits = sum(1 for doc_id in ranked[:k] if _is_relevant(doc_id, relevant))
    return hits / k


def recall_at_k(ranked: list, relevant: dict, k: int) -> float:
    """R@k = |relevant docs in top-k| / |all relevant docs|"""
    total_relevant = sum(1 for grade in relevant.values() if grade > 0)
    if total_relevant == 0:
        return 0.0  # nothing to find: recall is undefined, report 0.0
    hits = sum(1 for doc_id in ranked[:k] if _is_relevant(doc_id, relevant))
    return hits / total_relevant


def f1_at_k(ranked: list, relevant: dict, k: int) -> float:
    """F1@k = 2 * P * R / (P + R) - the harmonic mean, which (unlike the
    arithmetic mean) stays low when either half is low."""
    precision = precision_at_k(ranked, relevant, k)
    recall = recall_at_k(ranked, relevant, k)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def reciprocal_rank(ranked: list, relevant: dict) -> float:
    """RR = 1 / (rank of the first relevant result), ranks 1-based; 0.0 if none.

    MRR is the mean of this over all queries - run_eval does the averaging.
    Rewards getting *one* right answer to the top, which is the right shape
    for "find me that PDF someone sent" - the user wants one document.
    """
    for rank, doc_id in enumerate(ranked, start=1):
        if _is_relevant(doc_id, relevant):
            return 1 / rank
    return 0.0


def ndcg_at_k(ranked: list, relevant: dict, k: int) -> float:
    """nDCG@k = DCG@k / IDCG@k

        DCG@k  = sum_{i=1..k} grade_i / log2(i + 1)        (i 1-based)
        IDCG@k = the same sum over the ideal, grade-descending ordering

    The log2(i + 1) discount is what makes this rank-aware: a grade-3
    document is worth 3/log2(2) = 3.0 at rank 1 but only 3/log2(4) = 1.5 at
    rank 3. Dividing by the ideal normalizes to 0..1, so queries with
    different numbers of relevant documents can be averaged together.
    """
    def dcg(grades: list) -> float:
        return sum(grade / log2(i + 1) for i, grade in enumerate(grades[:k], start=1))

    actual = dcg([relevant.get(doc_id, 0) for doc_id in ranked])
    ideal = dcg(sorted(relevant.values(), reverse=True))
    if ideal == 0:
        return 0.0  # no relevant documents: nothing to normalize against
    return actual / ideal
