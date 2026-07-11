"""Plain-SQL schema migrations.

Numbered files in migrations/ at the repo root - 0001_initial.sql,
0002_add_whatever.sql, ... Each is applied exactly once, in filename order,
and recorded in the schema_migrations table. Two rules:

  1. Never edit a migration that anyone may have applied - add a new file.
  2. Plain SQL only; one migration per schema change, named for what it does.

ponytail: ~30 lines + a bookkeeping table instead of Alembic. Alembic pays off
when SQLAlchemy models exist to autogenerate diffs from; this codebase is raw
psycopg on purpose, so there is nothing to autogenerate. Revisit only if we
ever adopt an ORM.
"""

import logging
from pathlib import Path

from wadr.db import get_conn

log = logging.getLogger(__name__)

# repo-root/migrations (works because uv installs the project editable)
MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def migrate() -> list[str]:
    """Apply pending migrations in filename order; returns the filenames applied."""
    applied: list[str] = []
    with get_conn() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " filename TEXT PRIMARY KEY,"
            " applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        done = {r[0] for r in conn.execute("SELECT filename FROM schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
            conn.commit()  # one transaction per migration file
            log.info("applied %s", path.name)
            applied.append(path.name)
    return applied
