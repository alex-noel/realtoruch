-- Initial schema. Apply once in the indicated database as the schema owner.

BEGIN;


CREATE TABLE users (
	id VARCHAR(36) NOT NULL,
	email VARCHAR(254) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (email)
)

;

CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(50) PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP);

INSERT INTO schema_migrations(version) VALUES ('001_auth');

COMMIT;
