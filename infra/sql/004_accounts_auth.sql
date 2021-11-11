-- Apply in the auth database after 001_auth.sql.
BEGIN;
ALTER TABLE users ADD COLUMN verified_at TIMESTAMP;
ALTER TABLE users ADD COLUMN deleted_at TIMESTAMP;

CREATE TABLE auth_jobs (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	kind VARCHAR(20) NOT NULL,
	secret TEXT,
	status VARCHAR(20) NOT NULL,
	attempts INTEGER NOT NULL,
	next_attempt_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	lease_until TIMESTAMP WITHOUT TIME ZONE,
	last_error VARCHAR(100),
	PRIMARY KEY (id)
);

CREATE INDEX ix_auth_jobs_due ON auth_jobs (status, next_attempt_at);

CREATE INDEX ix_auth_jobs_user_id ON auth_jobs (user_id);

CREATE TABLE account_tokens (
	token_hash VARCHAR(64) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	kind VARCHAR(20) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	used_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (token_hash),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_account_tokens_user_id ON account_tokens (user_id);

CREATE TABLE login_sessions (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	label VARCHAR(120) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	last_used_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	revoked_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_login_sessions_user_id ON login_sessions (user_id);

CREATE TABLE refresh_tokens (
	token_hash VARCHAR(64) NOT NULL,
	session_id VARCHAR(36) NOT NULL,
	used_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (token_hash),
	FOREIGN KEY(session_id) REFERENCES login_sessions (id) ON DELETE CASCADE
);

CREATE INDEX ix_refresh_tokens_session_id ON refresh_tokens (session_id);

INSERT INTO schema_migrations(version) VALUES ('004_accounts_auth');
COMMIT;
