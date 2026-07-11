"""IR effectiveness metrics BY HAND. TODO(WS3).

HARD RULE: no sklearn / pytrec_eval / scipy - plain Python (math.log2 is
allowed). Viva evidence for the evaluation lecture; comment the formulas.

Conventions used by every function here:
    ranked:   ordered list of retrieved doc ids (best first)
    relevant: dict doc id -> graded relevance 0-3
Binary metrics treat grade > 0 as relevant.
"""


def precision_at_k(ranked: list, relevant: dict, k: int) -> float:
    """|relevant docs in top-k| / k."""
    raise NotImplementedError("TODO(WS3): precision@k")


def recall_at_k(ranked: list, relevant: dict, k: int) -> float:
    """|relevant docs in top-k| / |all relevant docs|. Define 0.0 when none relevant."""
    raise NotImplementedError("TODO(WS3): recall@k")


def f1_at_k(ranked: list, relevant: dict, k: int) -> float:
    """Harmonic mean of P@k and R@k; 0.0 when both are 0."""
    raise NotImplementedError("TODO(WS3): f1@k")


def reciprocal_rank(ranked: list, relevant: dict) -> float:
    """1 / rank of the first relevant result (1-based); 0.0 if none retrieved.

    MRR = mean of this over all queries (run_eval does the averaging).
    """
    raise NotImplementedError("TODO(WS3): reciprocal rank")


def ndcg_at_k(ranked: list, relevant: dict, k: int) -> float:
    """DCG@k / IDCG@k with DCG@k = sum_{i=1..k} grade_i / log2(i + 1) (i 1-based).

    IDCG is the DCG of the ideal (grade-descending) ordering; 0.0 when IDCG is 0.
    """
    raise NotImplementedError("TODO(WS3): nDCG@k")
