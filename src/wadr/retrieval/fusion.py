"""Reciprocal Rank Fusion: combine ranked lists whose scores aren't comparable."""

from datetime import UTC, datetime

RRF_K = 60

# A document re-shared today ranks as if it had 1.15x its fused score; that
# edge halves every 30 days. Calibrated against how flat RRF scores actually
# are: rank 1 beats rank 10 by 1.15x and rank 30 by only 1.48x, so 0.15 buys a
# same-day share roughly ten places - enough to break ties and surface the
# freshly forwarded copy, not enough to drag rank 30 to the top. Anything near
# 0.5 does overrule relevance outright (test_recency_boost_does_not_overrule).
RECENCY_WEIGHT = 0.15
RECENCY_HALF_LIFE_DAYS = 30.0


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


def recency_boost(
    fused: list[tuple],
    latest_sighting: dict,
    weight: float = RECENCY_WEIGHT,
    half_life_days: float = RECENCY_HALF_LIFE_DAYS,
    now: datetime | None = None,
) -> list[tuple]:
    """Re-rank so recently shared documents score higher:

        score(d) *= 1 + weight * 0.5 ** (age_days / half_life_days)

    `latest_sighting` maps the *same ids `fused` uses* to that item's newest
    sightings.sent_at; ids missing from it keep their score unchanged. Pure
    function - pass `now` to test it. Returns (id, score) sorted descending.
    """
    now = now or datetime.now(UTC)
    boosted = []
    for item, score in fused:
        sent_at = latest_sighting.get(item)
        if sent_at is None:
            boosted.append((item, score))
            continue
        if sent_at.tzinfo is None:  # a naive timestamp would blow up the subtraction
            sent_at = sent_at.replace(tzinfo=UTC)
        age_days = max((now - sent_at).total_seconds() / 86400, 0.0)  # clock skew -> 0
        boosted.append((item, score * (1 + weight * 0.5 ** (age_days / half_life_days))))
    return sorted(boosted, key=lambda kv: kv[1], reverse=True)
