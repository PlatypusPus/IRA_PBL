-- 0005: the weekly "what did I miss" digest.
--
-- One row per user, remembering how far the last digest reached. Without it a
-- fixed "last 7 days" window would silently swallow whatever arrived while a
-- run was skipped - which is precisely the thing this feature exists to stop.
CREATE TABLE digest_runs (
    user_id      BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    last_sent_at TIMESTAMPTZ NOT NULL
);
