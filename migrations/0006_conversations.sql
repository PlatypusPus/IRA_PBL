-- 0006: more than one conversation per user, so a search thread can be kept,
-- started fresh, or thrown away.
--
-- No title column: the first thing you asked IS the title of the conversation,
-- and deriving it means it can never drift from the messages.
CREATE TABLE conversations (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX conversations_user_idx ON conversations (user_id, id DESC);

ALTER TABLE chat_messages ADD COLUMN conversation_id BIGINT
    REFERENCES conversations(id) ON DELETE CASCADE;

-- Existing history keeps working: everything a user has said so far becomes
-- their first conversation.
INSERT INTO conversations (user_id, created_at)
SELECT user_id, min(created_at) FROM chat_messages GROUP BY user_id;

UPDATE chat_messages m SET conversation_id = c.id
  FROM conversations c
 WHERE c.user_id = m.user_id AND m.conversation_id IS NULL;

ALTER TABLE chat_messages ALTER COLUMN conversation_id SET NOT NULL;
CREATE INDEX chat_messages_conversation_idx ON chat_messages (conversation_id, created_at);
