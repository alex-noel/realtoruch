-- Apply after 002_alerts.sql, as the schema owner.
BEGIN;

CREATE TABLE email_subscriptions (
	user_id VARCHAR(36) NOT NULL,
	email VARCHAR(254) NOT NULL,
	enabled BOOLEAN NOT NULL,
	verified_at TIMESTAMP WITHOUT TIME ZONE,
	verification_hash VARCHAR(64),
	verification_expires_at TIMESTAMP WITHOUT TIME ZONE,
	requested_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	unsubscribe_token VARCHAR(64) NOT NULL,
	PRIMARY KEY (user_id),
	UNIQUE (verification_hash),
	UNIQUE (unsubscribe_token)
);

CREATE TABLE email_deliveries (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	notification_id VARCHAR(36),
	confirmation_token VARCHAR(64),
	status VARCHAR(20) NOT NULL,
	attempts INTEGER NOT NULL,
	next_attempt_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	lease_until TIMESTAMP WITHOUT TIME ZONE,
	last_error VARCHAR(100),
	delivered_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES email_subscriptions (user_id),
	UNIQUE (notification_id),
	FOREIGN KEY(notification_id) REFERENCES notifications (id)
);

CREATE INDEX ix_email_due ON email_deliveries (status, next_attempt_at);

INSERT INTO schema_migrations(version) VALUES ('003_email_alerts');

COMMIT;
