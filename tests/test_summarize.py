"""Summaries: written by a model when there is one, by the document when not."""

import base64
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import wadr.api.app as appmod
from wadr import accounts, summarize
from wadr.db import get_conn
from wadr.retrieval import service

NOTICE = (
    "St Joseph Engineering College, Mangaluru\n"
    "NOTICE: Summer Semester End Examination (SEE) - September 2026. "
    "This notice is issued in response to queries received from students "
    "regarding their eligibility to appear for the examination."
)


@pytest.fixture
def document():
    """A document row with text and no summary yet."""
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    with get_conn() as conn:
        doc_id = conn.execute(
            "INSERT INTO documents (file_hash, filename, mime_type, extracted_text)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            (f"hash-{stamp}", f"wa-{stamp}.jpeg", "image/jpeg", NOTICE),
        ).fetchone()[0]
    yield doc_id
    with get_conn() as conn:
        conn.execute("DELETE FROM documents WHERE id = %s", (doc_id,))


def test_without_a_model_it_uses_the_documents_own_first_sentence(monkeypatch):
    monkeypatch.setattr(summarize, "MODEL", "")
    out = summarize.summarize(NOTICE)
    assert "Summer Semester End Examination" in out
    assert "\n" not in out
    assert len(out) <= summarize.MAX_CHARS + 1  # the ellipsis


def test_a_model_answer_is_used_and_tidied(monkeypatch):
    monkeypatch.setattr(summarize, "MODEL", "test-model")
    monkeypatch.setattr(
        summarize, "_generate",
        lambda text: '  "This document is a notice about\nexam eligibility."  ',
    )
    # quotes stripped, newline flattened, "This document is a" dropped as noise
    assert summarize.summarize(NOTICE) == "Notice about exam eligibility."


@pytest.mark.parametrize("written, expected", [
    # every preamble llama3.2:3b actually produced on this corpus
    ("This is a job application notice for the editorial committee.",
     "Job application notice for the editorial committee."),
    ("This appears to be a garbled document.", "Garbled document."),
    ("The document is a mentor-mentee assignment list.", "Mentor-mentee assignment list."),
    # a sentence that simply starts with a real word must survive intact
    ("Notification for exam form submission.", "Notification for exam form submission."),
])
def test_model_preamble_is_stripped(monkeypatch, written, expected):
    monkeypatch.setattr(summarize, "MODEL", "test-model")
    monkeypatch.setattr(summarize, "_generate", lambda text: written)
    assert summarize.summarize(NOTICE) == expected


def test_only_the_first_sentence_survives_but_abbreviations_do(monkeypatch):
    """One sentence was asked for; a second one cut mid-word reads as a bug."""
    monkeypatch.setattr(summarize, "MODEL", "test-model")
    monkeypatch.setattr(
        summarize, "_generate",
        lambda text: "Grade cards are due on 31 August 2026. Document type: circular.",
    )
    assert summarize.summarize(NOTICE) == "Grade cards are due on 31 August 2026."

    # "St." is an abbreviation, not the end of a sentence
    monkeypatch.setattr(
        summarize, "_generate",
        lambda text: "Workshop proposal for St. Joseph Engineering College, Mangaluru.",
    )
    assert "Mangaluru" in summarize.summarize(NOTICE)


def test_a_model_that_is_down_still_produces_something(monkeypatch):
    monkeypatch.setattr(summarize, "MODEL", "test-model")
    monkeypatch.setattr(summarize, "_generate", lambda text: None)
    assert "Summer Semester" in summarize.summarize(NOTICE)


def test_a_long_answer_is_cut_at_a_word(monkeypatch):
    monkeypatch.setattr(summarize, "MODEL", "test-model")
    monkeypatch.setattr(summarize, "_generate", lambda text: "word " * 100)
    out = summarize.summarize(NOTICE)
    assert out.endswith("…")
    assert len(out) <= summarize.MAX_CHARS + 1


def test_garbled_ocr_is_not_quoted_back(monkeypatch):
    """A blurred photo OCRs as rubble; saying nothing beats saying that."""
    monkeypatch.setattr(summarize, "MODEL", "")
    junk = "Lv ik: oi 7 EY m4 mo 72 26 aN LIF Let Lod jh aon HE (17S 12)(_ yale aR"
    assert summarize.summarize(junk) == ""
    # a real letterhead, all caps and abbreviations, must still pass
    assert summarize.summarize(
        "ST JOSEPH ENGINEERING COLLEGE, MANGALURU (An Autonomous Institution)"
    )


def test_an_empty_document_gets_no_summary():
    assert summarize.summarize("   ") == ""


def test_the_summary_is_written_once_and_reused(document, monkeypatch):
    calls = []
    monkeypatch.setattr(summarize, "MODEL", "test-model")
    monkeypatch.setattr(
        summarize, "_generate",
        lambda text: calls.append(text) or "Exam eligibility notice.",
    )
    with get_conn() as conn:
        first = summarize.for_document(conn, document)
    with get_conn() as conn:
        second = summarize.for_document(conn, document)

    assert first == second == "Exam eligibility notice."
    assert len(calls) == 1, "the second call must come from the stored summary"

    with get_conn() as conn:
        stored = conn.execute(
            "SELECT summary FROM documents WHERE id = %s", (document,)
        ).fetchone()[0]
    assert stored == "Exam eligibility notice."


def test_search_shows_the_summary_and_hides_rubble(monkeypatch):
    """The case this is for: a meaningless filename whose page OCR'd to junk."""
    monkeypatch.setattr(appmod, "BRIDGE_TOKEN", "test-token")
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    email = f"cards-{stamp}@test.invalid"
    filename = f"1787227836920-{stamp}.txt"  # the meaningless kind WhatsApp produces

    client = TestClient(appmod.app)
    client.post("/api/auth/signup", json={"email": email, "password": "hunter2hunter2"})
    user = accounts.user_for_token(client.cookies["wadr_session"])
    account = accounts.create_account(user["id"], "phone")
    try:
        garbled = f"{stamp} Lv ik: oi 7 EY m4 mo 72 26 aN LIF Let Lod jh aon HE (17S 12)(_ aR"
        res = client.post(
            "/api/bridge/document",
            headers={"X-Bridge-Token": "test-token"},
            json={
                "session_key": account["session_key"], "chat_id": "g@us", "sender": "Class",
                "timestamp": datetime.now(UTC).isoformat(), "filename": filename,
                "mime_type": "text/plain",
                "data_base64": base64.b64encode(garbled.encode()).decode(),
            },
        )
        assert res.status_code == 200
        written = "Revised timetable for 1st and 2nd year UG programmes."
        with get_conn() as conn:
            conn.execute(
                "UPDATE documents SET summary = %s WHERE id = %s",
                (written, res.json()["document_id"]),
            )

        hits = service.search(stamp, user["id"])
        assert hits, "the document should still be findable"
        assert hits[0].summary == written
        assert hits[0].snippet == "", "OCR rubble must not be shown as a snippet"
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM users WHERE email = %s", (email,))
            conn.execute("DELETE FROM documents WHERE filename = %s", (filename,))


def test_an_unknown_document_is_not_an_error():
    with get_conn() as conn:
        assert summarize.for_document(conn, 999_999_999) == ""
