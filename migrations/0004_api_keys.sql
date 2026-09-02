-- 0004: API keys, so an agent (Claude, or anything speaking MCP) can act for
-- one account without holding that user's password or browser session.

CREATE TABLE api_keys (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label        TEXT NOT NULL DEFAULT '',
    -- SHA-256 of the key, never the key itself: a leaked database dump must not
    -- hand over working credentials. The plaintext is shown once, at creation.
    key_hash     TEXT NOT NULL UNIQUE,
    prefix       TEXT NOT NULL,          -- first 8 chars, so the UI can identify it
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ
);
CREATE INDEX api_keys_user_idx ON api_keys (user_id);
