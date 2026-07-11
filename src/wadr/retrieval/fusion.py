"""Reciprocal Rank Fusion: combine ranked lists whose scores aren't comparable."""

RRF_K = 60


def rrf(rankings: list[list], k: int = RRF_K) -> list[tuple]:
    """Fuse ranked lists of ids (any hashable):

        score(d) = sum over lists containing d of 1 / (k + rank_d),  rank 1-based

    Items missing from a list contribute nothing for that list. Returns
    (id, score) pairs sorted by descending score.
    """
    scores: dict = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


def recency_boost(fused: list[tuple], latest_sighting_by_doc: dict) -> list[tuple]:
    """TODO(WS4): re-rank so recently shared documents score higher.

    Suggested: score *= 1 + w * exp(-age_days / half_life) using the newest
    sightings.sent_at per document; pick w and half_life empirically and note
    them in TODO.md. Keep this a pure function so it stays unit-testable.
    """
    raise NotImplementedError("TODO(WS4): recency boost")
