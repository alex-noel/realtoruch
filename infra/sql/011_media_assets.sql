CREATE TABLE media_assets (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    state VARCHAR(20) NOT NULL CHECK (state IN ('pending', 'ready', 'rejected', 'deleted')),
    digest VARCHAR(64),
    description VARCHAR(500) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, idempotency_key)
);
CREATE INDEX ix_media_assets_user_id ON media_assets (user_id);
