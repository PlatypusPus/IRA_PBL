"""A linked number sits in group chats full of other people, and anyone can
type /find in one. The owner may search everything that number received; a
group member may only reach what they could already see."""

import base64
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import wadr.api.app as appmod
from wadr import accounts
from wadr.adapters import openwa
from wadr.db import get_conn
from wadr.retrieval import service

OWNER = "919999900000@s.whatsapp.net"
STRANGER = "918888800000@s.whatsapp.net"
GROUP = "group-a@g.us"
PRIVATE = "919111100000@s.whatsapp.net"


@pytest.fixture
def linked(monkeypatch):
    """One linked number holding a private document and a group document."""
    monkeypatch.setattr(appmod, "BRIDGE_TOKEN", "test-token")
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    email = f"privacy-{stamp}@test.invalid"

    client = TestClient(appmod.app)
    client.post("/api/auth/signup", json={"email": email, "password": "hunter2hunter2"})
    user = accounts.user_for_token(client.cookies["wadr_session"])
    account = accounts.create_account(user["id"], "phone")

    def receive(chat, sender, tag):
        filename = f"{tag}-{stamp}.txt"
        res = client.post(
            "/api/bridge/document",
            headers={"X-Bridge-Token": "test-token"},
            json={
                "session_key": account["session_key"], "chat_id": chat, "sender": sender,
                "timestamp": datetime.now(UTC).isoformat(), "filename": filename,
                "mime_type": "text/plain",
                "data_base64": base64.b64encode(
                    f"salary payslip {tag} {stamp}".encode()
                ).decode(),
            },
        )
        assert res.status_code == 200
        return {"filename": filename, "document_id": res.json()["document_id"]}

    docs = {
        # the owner's private business, in a one-to-one chat
        "private": receive(PRIVATE, PRIVATE, "private"),
        # shared in the group the stranger is also in
        "group": receive(GROUP, "917777700000@s.whatsapp.net", "group"),
        # sent by the stranger, but into a chat they are not asking from
        "theirs": receive(PRIVATE, STRANGER, "theirs"),
    }

    yield {"user": user, "session_key": account["session_key"], "docs": docs, "stamp": stamp}

    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE email = %s", (email,))
        for doc in docs.values():
            conn.execute("DELETE FROM documents WHERE filename = %s", (doc["filename"],))


def _found(linked, seen_by):
    hits = service.search(f"payslip {linked['stamp']}", linked["user"]["id"], seen_by=seen_by)
    return {h.filename for h in hits}


def test_the_owner_finds_everything_their_number_received(linked):
    found = _found(linked, None)
    assert found == {d["filename"] for d in linked["docs"].values()}


def test_a_group_member_never_sees_the_owners_private_chat(linked):
    found = _found(linked, (STRANGER, GROUP))
    assert linked["docs"]["private"]["filename"] not in found


def test_a_group_member_sees_files_shared_in_that_group(linked):
    assert linked["docs"]["group"]["filename"] in _found(linked, (STRANGER, GROUP))


def test_a_group_member_sees_files_they_sent_themselves(linked):
    # sent by them into a private chat: they already have it, it is not a leak
    assert linked["docs"]["theirs"]["filename"] in _found(linked, (STRANGER, GROUP))


def test_a_stranger_cannot_download_what_they_cannot_find(linked):
    private = linked["docs"]["private"]["document_id"]
    assert service.get_document(private, linked["user"]["id"]) is not None
    assert service.get_document(private, linked["user"]["id"], seen_by=(STRANGER, GROUP)) is None


def test_a_partial_number_is_not_a_match(linked):
    """Exact equality, not ILIKE: a prefix of someone's number is not them."""
    assert _found(linked, ("9188", "group-a")) == set()


def test_find_in_a_group_is_scoped_but_the_owners_own_find_is_not(linked, monkeypatch):
    sent = []
    monkeypatch.setattr(
        openwa.OpenWAAdapter, "send_text", lambda self, cid, txt: sent.append(txt)
    )
    base = {"session_key": linked["session_key"], "chat_id": GROUP,
            "text": f"/find payslip {linked['stamp']}"}

    openwa.OpenWAAdapter().handle_query({**base, "sender": STRANGER, "from_me": False})
    assert linked["docs"]["private"]["filename"] not in sent[-1]
    assert linked["docs"]["group"]["filename"] in sent[-1]

    openwa.OpenWAAdapter().handle_query({**base, "sender": OWNER, "from_me": True})
    assert linked["docs"]["private"]["filename"] in sent[-1]


def test_get_state_is_per_person_not_per_chat(linked, monkeypatch):
    """Two people searching in one group must not renumber each other."""
    sent = []
    monkeypatch.setattr(
        openwa.OpenWAAdapter, "send_text", lambda self, cid, txt: sent.append(txt)
    )
    openwa._last_results[(linked["session_key"], GROUP, OWNER)] = [1, 2, 3]
    openwa.OpenWAAdapter().handle_get(
        {"session_key": linked["session_key"], "chat_id": GROUP,
         "sender": STRANGER, "from_me": False, "text": "/get 1"}
    )
    assert "find" in sent[-1].lower()  # the stranger has no search of their own
