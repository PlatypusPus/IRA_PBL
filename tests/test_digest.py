"""The weekly digest: what arrived, to whom, and only once."""

import base64
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import wadr.api.app as appmod
from wadr import accounts, digest
from wadr.db import get_conn


@pytest.fixture
def user(monkeypatch):
    """A linked number with one freshly received document."""
    monkeypatch.setattr(appmod, "BRIDGE_TOKEN", "test-token")
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    email = f"digest-{stamp}@test.invalid"

    client = TestClient(appmod.app)
    client.post("/api/auth/signup", json={"email": email, "password": "hunter2hunter2"})
    account_owner = accounts.user_for_token(client.cookies["wadr_session"])
    account = accounts.create_account(account_owner["id"], "phone")
    accounts.mark_linked(account["session_key"], "919999900000", "linked")

    filename = f"digest-note-{stamp}.txt"
    res = client.post(
        "/api/bridge/document",
        headers={"X-Bridge-Token": "test-token"},
        json={
            "session_key": account["session_key"], "chat_id": "g@us", "sender": "Priya",
            "timestamp": datetime.now(UTC).isoformat(), "filename": filename,
            "mime_type": "text/plain",
            "data_base64": base64.b64encode(f"lease renewal {stamp}".encode()).decode(),
        },
    )
    assert res.status_code == 200

    yield {"id": account_owner["id"], "filename": filename, "session_key": account["session_key"]}

    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE email = %s", (email,))
        conn.execute("DELETE FROM documents WHERE filename = %s", (filename,))


def test_digest_lists_what_arrived(user):
    text = digest.build(user["id"])
    assert user["filename"] in text
    assert "Priya" in text
    assert "*1 new document*" in text  # singular, not "1 new documents"


def test_a_user_with_nothing_new_gets_no_message():
    with get_conn() as conn:
        row = conn.execute("SELECT max(id) + 1 FROM users").fetchone()
    assert digest.build(row[0]) is None


def test_sending_consumes_the_window_so_it_is_not_repeated(user, monkeypatch):
    outbox = []
    monkeypatch.setattr(
        digest.bridge_client, "send_text",
        lambda key, chat, text: outbox.append((key, chat, text)) or {},
    )

    assert digest.send(user["id"]) is not None
    assert len(outbox) == 1
    assert outbox[0][0] == user["session_key"]
    assert outbox[0][1] == "919999900000@s.whatsapp.net"  # the user's own chat
    assert digest.send(user["id"]) is None  # nothing new since


def test_a_failed_send_keeps_the_window_open(user, monkeypatch):
    # A bridge that was down for the weekly run must not erase the week it
    # failed to report.
    monkeypatch.setattr(
        digest.bridge_client, "send_text",
        lambda *_: {"status": "bridge_offline", "detail": "not running"},
    )
    assert digest.send(user["id"]) is None
    assert digest.build(user["id"]) is not None


def test_a_document_timestamped_in_the_future_is_not_repeated(user, monkeypatch):
    """WhatsApp timestamps come from the sender's phone, whose clock may be
    ahead of this database - marking the window with now() alone would report
    the same file in every digest until the clocks met."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE sightings SET sent_at = now() + interval '2 hours'"
            " WHERE document_id IN (SELECT id FROM documents WHERE filename = %s)",
            (user["filename"],),
        )
    monkeypatch.setattr(digest.bridge_client, "send_text", lambda *_: {})
    assert digest.send(user["id"]) is not None
    assert digest.send(user["id"]) is None


def test_long_digests_are_truncated_with_a_count():
    arrivals = [(f"file-{i}.pdf", "Dad", datetime.now(UTC)) for i in range(digest.MAX_LISTED + 4)]
    text = digest.compose(arrivals)
    assert f"*{len(arrivals)} new documents*" in text
    assert "…and 4 more" in text
    assert "file-0.pdf" in text
    assert f"file-{len(arrivals) - 1}.pdf" not in text
