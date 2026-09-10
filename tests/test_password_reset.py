"""Passwords are one-way hashes, so the recovery path is replacement."""

from datetime import UTC, datetime

import pytest

from wadr import accounts
from wadr.db import get_conn


@pytest.fixture
def account():
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    email = f"reset-{stamp}@test.invalid"
    accounts.sign_up(email, "originalpassword")
    yield email
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE email = %s", (email,))


def test_the_plaintext_is_never_stored(account):
    with get_conn() as conn:
        stored = conn.execute(
            "SELECT password_hash FROM users WHERE email = %s", (account,)
        ).fetchone()[0]
    assert "originalpassword" not in stored
    assert stored.startswith("scrypt$")
    assert accounts.verify_password("originalpassword", stored)


def test_two_accounts_with_one_password_get_different_hashes():
    """Salted: identical passwords must not produce identical hashes."""
    assert accounts.hash_password("same password") != accounts.hash_password("same password")


def test_setting_a_new_password_lets_you_back_in(account):
    accounts.set_password(account, "a brand new password")
    assert accounts.log_in(account, "a brand new password")
    with pytest.raises(accounts.AuthError):
        accounts.log_in(account, "originalpassword")


def test_changing_a_password_signs_out_existing_sessions(account):
    token = accounts.log_in(account, "originalpassword")
    assert accounts.user_for_token(token) is not None
    accounts.set_password(account, "a brand new password")
    assert accounts.user_for_token(token) is None


def test_a_short_password_is_refused_and_the_old_one_still_works(account):
    with pytest.raises(accounts.AuthError):
        accounts.set_password(account, "short")
    assert accounts.log_in(account, "originalpassword")


def test_an_unknown_address_is_refused(account):
    with pytest.raises(accounts.AuthError):
        accounts.set_password("nobody@test.invalid", "a brand new password")
