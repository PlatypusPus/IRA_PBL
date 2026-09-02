-- 0003: multi-tenant product schema. Accounts own linked WhatsApp numbers;
-- a document is visible to you because one of YOUR numbers saw it.

CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,          -- scrypt, "scrypt$<salt hex>$<key hex>"
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Opaque bearer tokens kept server-side so a logout can actually revoke.
CREATE TABLE sessions (
    token      TEXT PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX sessions_user_idx ON sessions (user_id);

-- One linked WhatsApp number. A user may link several (personal, work, ...);
-- session_key names the bridge's Baileys auth folder for that number.
CREATE TABLE whatsapp_accounts (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label       TEXT NOT NULL DEFAULT '',
    phone       TEXT,                     -- learned from WhatsApp once linked
    session_key TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending | linked | logged_out
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX whatsapp_accounts_user_idx ON whatsapp_accounts (user_id);

-- Dedupe stays global (identical bytes = one document, one extraction), but
-- VISIBILITY is per sighting: your search only ever sees documents one of your
-- own numbers received. Nullable so pre-existing CLI-ingested rows survive.
ALTER TABLE sightings ADD COLUMN account_id BIGINT
    REFERENCES whatsapp_accounts(id) ON DELETE CASCADE;
CREATE INDEX sightings_account_idx ON sightings (account_id);

-- Chat transcript, so a conversation survives a reload.
CREATE TABLE chat_messages (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,             -- 'user' | 'assistant'
    text       TEXT NOT NULL,
    results    JSONB,                     -- documents cited, for re-render
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX chat_messages_user_idx ON chat_messages (user_id, created_at);
