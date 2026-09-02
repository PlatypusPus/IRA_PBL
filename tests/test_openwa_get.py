"""/get guard logic - the parts that reply before touching the DB.

Every bridge payload now carries a session_key naming the linked number it
arrived on, so the adapter is stubbed to resolve one without a database.
"""

import pytest

from wadr.adapters import openwa

SESSION = "u1-test"
CHAT = "c@x"


@pytest.fixture
def sent(monkeypatch):
    captured = []
    monkeypatch.setattr(
        openwa.OpenWAAdapter, "send_text", lambda self, cid, txt: captured.append(txt)
    )
    monkeypatch.setattr(
        openwa, "account_for_session_key", lambda key: {"id": 1, "user_id": 1}
    )
    openwa._last_results.pop((SESSION, CHAT), None)
    return captured


def _get(text):
    openwa.OpenWAAdapter().handle_get(
        {"session_key": SESSION, "chat_id": CHAT, "text": text}
    )


def test_get_without_prior_search_tells_user_to_find_first(sent):
    _get("/get 1")
    assert sent and "find" in sent[0].lower()


def test_get_out_of_range_reports_valid_range(sent):
    openwa._last_results[(SESSION, CHAT)] = [10, 11]
    _get("/get 9")
    assert sent and "1-2" in sent[0]


def test_get_non_numeric_is_rejected(sent):
    openwa._last_results[(SESSION, CHAT)] = [10, 11]
    _get("/get two")
    assert sent and "Usage" in sent[0]


def test_unknown_session_is_refused(monkeypatch):
    """A session_key with no linked number behind it must not be served."""
    monkeypatch.setattr(openwa, "account_for_session_key", lambda key: None)
    with pytest.raises(openwa.UnknownSession):
        _get("/get 1")


def test_last_results_are_per_number(sent):
    """Two linked numbers in the same chat id must not share /get state."""
    openwa._last_results[(SESSION, CHAT)] = [10, 11]
    openwa.OpenWAAdapter().handle_get(
        {"session_key": "u2-other", "chat_id": CHAT, "text": "/get 1"}
    )
    assert sent and "find" in sent[0].lower()
