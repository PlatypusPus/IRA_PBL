"""BM25 tokenisation: "1st and 2nd year" has to reach "I and II Year B.E.".

No database - this is the tokeniser both the query and the documents run
through, so testing it directly tests the match.
"""

from wadr.retrieval.bm25_model import _tokenize

NOTICE = "Eligibility of I and II Year B.E, Students for the Summer Semester"


def shared(query: str, document: str) -> set[str]:
    return set(_tokenize(query)) & set(_tokenize(document))


def test_the_case_this_exists_for():
    # measured before: only {and, year} overlapped, and BM25 ranked it 5th
    assert "2" in shared("1st and 2nd year", NOTICE)


def test_spelled_out_ordinals_reach_numerals():
    assert "2" in shared("second year", NOTICE)
    assert _tokenize("fourth semester") == ["4", "semester"]


def test_digit_ordinals_lose_their_suffix():
    assert _tokenize("1st 2nd 3rd 4th 22nd") == ["1", "2", "3", "4", "22"]


def test_a_lone_i_stays_a_word():
    """"i" is the English pronoun far more often than it is the numeral one."""
    assert _tokenize("i think i lost it") == ["i", "think", "i", "lost", "it"]
    assert "1" not in _tokenize(NOTICE)


def test_ordinary_words_are_untouched():
    assert _tokenize("Invoice INV-4471 from Dad") == ["invoice", "inv", "4471", "from", "dad"]
