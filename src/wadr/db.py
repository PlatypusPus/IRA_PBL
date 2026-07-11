"""Postgres connection layer. One env var, one function."""

import os

import psycopg

DATABASE_URL = os.environ.get("WADR_DATABASE_URL", "postgresql://wadr:wadr@localhost:5433/wadr")


def get_conn() -> psycopg.Connection:
    """New connection. Use as `with get_conn() as conn:` - commits on success,
    rolls back on exception, closes either way."""
    return psycopg.connect(DATABASE_URL)


def to_vector(embedding: list[float]) -> str:
    """Format a float list as a pgvector literal; pair with a ::vector cast in SQL.

    ponytail: string literal instead of the pgvector python adapter - one less dep.
    """
    return "[" + ",".join(str(x) for x in embedding) + "]"
