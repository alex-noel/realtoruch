ALTER TABLE conversations
    ADD COLUMN renter_read_message_id VARCHAR(36),
    ADD COLUMN owner_read_message_id VARCHAR(36);

CREATE INDEX ix_conversations_renter_order ON conversations (renter_id, updated_at, id);
CREATE INDEX ix_conversations_owner_order ON conversations (owner_id, updated_at, id);
CREATE INDEX ix_message_thread_order ON messages (conversation_id, created_at, id);
