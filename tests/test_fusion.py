import pytest

from wadr.retrieval.fusion import rrf


def test_item_in_both_lists_outranks_single_list_items():
    fused = rrf([["a", "b", "c"], ["b", "d"]])
    assert fused[0][0] == "b"


def test_scores_are_reciprocal_rank_sums():
    fused = dict(rrf([["a", "b"], ["b", "a"]], k=60))
    expected = 1 / 61 + 1 / 62  # rank 1 in one list, rank 2 in the other
    assert fused["a"] == pytest.approx(expected)
    assert fused["b"] == pytest.approx(expected)


def test_default_k_is_60():
    ((item, score),) = rrf([["only"]])
    assert item == "only"
    assert score == pytest.approx(1 / 61)


def test_missing_items_contribute_nothing():
    fused = dict(rrf([["a"], ["b"]], k=60))
    assert fused["a"] == pytest.approx(1 / 61)
    assert fused["b"] == pytest.approx(1 / 61)
