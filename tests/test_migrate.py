import pytest


def _skip_without_db():
    import psycopg

    from wadr.db import DATABASE_URL

    try:
        psycopg.connect(DATABASE_URL, connect_timeout=2).close()
    except psycopg.OperationalError:
        pytest.skip("Postgres not running - `docker compose up -d` to enable this test")


def test_migrate_applies_everything_then_is_idempotent():
    _skip_without_db()
    from wadr.migrate import migrate

    migrate()  # brings any fresh DB fully up (no-op on an up-to-date one)
    assert migrate() == []  # second run: nothing pending
