"""Conversations: start one, clear one, and never touch someone else's."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import wadr.api.app as appmod
from wadr import chat
from wadr.db import get_conn


def _signup():
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    email = f"chat-{stamp}@test.invalid"
    client = TestClient(appmod.app)
    user = client.post(
        "/api/auth/signup", json={"email": email, "password": "hunter2hunter2"}
    ).json()
    return client, user, email


@pytest.fixture
def two_users():
    a, user_a, email_a = _signup()
    b, user_b, email_b = _signup()
    yield {"a": a, "b": b, "user_a": user_a, "user_b": user_b}
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE email = ANY(%s)", ([email_a, email_b],))


def test_the_first_message_creates_the_conversation(two_users):
    client = two_users["a"]
    assert client.get("/api/conversations").json() == []

    reply = client.post("/api/chat", json={"text": "the exam timetable"}).json()
    listed = client.get("/api/conversations").json()
    assert len(listed) == 1
    assert listed[0]["id"] == reply["conversation_id"]
    # the title is derived from what was asked, never stored separately
    assert listed[0]["title"] == "the exam timetable"


def test_messages_stay_in_their_own_conversation(two_users):
    client = two_users["a"]
    first = client.post("/api/chat", json={"text": "invoices"}).json()["conversation_id"]
    second = client.post("/api/chat", json={"text": "timetable"}).json()["conversation_id"]
    assert first != second

    texts = [m["text"] for m in client.get(f"/api/chat?conversation_id={first}").json()]
    assert "invoices" in texts
    assert "timetable" not in texts


def test_deleting_a_conversation_clears_its_messages(two_users):
    client = two_users["a"]
    cid = client.post("/api/chat", json={"text": "payslip"}).json()["conversation_id"]

    assert client.delete(f"/api/conversations/{cid}").status_code == 200
    assert client.get("/api/conversations").json() == []
    assert client.get(f"/api/chat?conversation_id={cid}").status_code == 404
    with get_conn() as conn:
        left = conn.execute(
            "SELECT count(*) FROM chat_messages WHERE conversation_id = %s", (cid,)
        ).fetchone()[0]
    assert left == 0  # cascaded, not orphaned


def test_another_users_conversation_is_invisible_and_untouchable(two_users):
    mine = two_users["a"].post(
        "/api/chat", json={"text": "my private search"}
    ).json()["conversation_id"]
    other = two_users["b"]

    assert other.get("/api/conversations").json() == []
    assert other.get(f"/api/chat?conversation_id={mine}").status_code == 404
    assert other.delete(f"/api/conversations/{mine}").status_code == 404
    assert other.post(
        "/api/chat", json={"text": "hello", "conversation_id": mine}
    ).status_code == 404
    # and it survived all of that
    assert len(two_users["a"].get(f"/api/chat?conversation_id={mine}").json()) == 2


def test_posting_into_a_conversation_that_does_not_exist(two_users):
    with pytest.raises(chat.NotYours):
        chat.answer(two_users["user_a"]["id"], "hello", 999_999_999)
