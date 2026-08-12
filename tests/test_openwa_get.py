"""/get guard logic - the parts that reply before touching the DB."""

from wadr.adapters import openwa


def _capture_text(monkeypatch):
    sent = []
    monkeypatch.setattr(
        openwa.OpenWAAdapter, "send_text", lambda self, cid, txt: sent.append(txt)
    )
    return sent


def test_get_without_prior_search_tells_user_to_find_first(monkeypatch):
    sent = _capture_text(monkeypatch)
    openwa._last_results.pop("c@x", None)
    openwa.OpenWAAdapter().handle_get({"chat_id": "c@x", "text": "/get 1"})
    assert sent and "find" in sent[0].lower()


def test_get_out_of_range_reports_valid_range(monkeypatch):
    sent = _capture_text(monkeypatch)
    openwa._last_results["c@x"] = [10, 11]
    openwa.OpenWAAdapter().handle_get({"chat_id": "c@x", "text": "/get 9"})
    assert sent and "1-2" in sent[0]


def test_get_non_numeric_is_rejected(monkeypatch):
    sent = _capture_text(monkeypatch)
    openwa._last_results["c@x"] = [10, 11]
    openwa.OpenWAAdapter().handle_get({"chat_id": "c@x", "text": "/get two"})
    assert sent and "Usage" in sent[0]
