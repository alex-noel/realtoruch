-- Apply in rentals after 003_email_alerts.sql.
BEGIN;
ALTER TABLE listings ADD COLUMN hidden BOOLEAN NOT NULL DEFAULT false;

CREATE TABLE advertiser_profiles (
	user_id VARCHAR(36) NOT NULL,
	name VARCHAR(100) NOT NULL,
	kind VARCHAR(20) NOT NULL,
	description VARCHAR(2000) NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (user_id)
);

CREATE TABLE collection_runs (
	id VARCHAR(36) NOT NULL,
	source VARCHAR(40) NOT NULL,
	city VARCHAR(100) NOT NULL,
	status VARCHAR(20) NOT NULL,
	started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	finished_at TIMESTAMP WITHOUT TIME ZONE,
	report JSON NOT NULL,
	PRIMARY KEY (id)
);

CREATE INDEX ix_collection_source_time ON collection_runs (source, started_at);

CREATE TABLE source_poll_state (
	source VARCHAR(40) NOT NULL,
	lease_id VARCHAR(36),
	lease_until TIMESTAMP WITHOUT TIME ZONE,
	retry_after TIMESTAMP WITHOUT TIME ZONE,
	failures INTEGER NOT NULL,
	last_success_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (source)
);

CREATE TABLE adverts (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	listing_id VARCHAR(36),
	draft JSON NOT NULL,
	state VARCHAR(20) NOT NULL,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES advertiser_profiles (user_id),
	FOREIGN KEY(listing_id) REFERENCES listings (id)
);

CREATE INDEX ix_adverts_listing_id ON adverts (listing_id);

CREATE INDEX ix_adverts_user_id ON adverts (user_id);

CREATE TABLE moderation_actions (
	id VARCHAR(36) NOT NULL,
	listing_id VARCHAR(36) NOT NULL,
	moderator_id VARCHAR(36) NOT NULL,
	action VARCHAR(20) NOT NULL,
	reason VARCHAR(1000) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(listing_id) REFERENCES listings (id)
);

CREATE INDEX ix_moderation_actions_listing_id ON moderation_actions (listing_id);

CREATE TABLE conversations (
	id VARCHAR(36) NOT NULL,
	advert_id VARCHAR(36) NOT NULL,
	renter_id VARCHAR(36) NOT NULL,
	owner_id VARCHAR(36) NOT NULL,
	renter_read_at TIMESTAMP WITHOUT TIME ZONE,
	owner_read_at TIMESTAMP WITHOUT TIME ZONE,
	blocked_by VARCHAR(36),
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (advert_id, renter_id),
	FOREIGN KEY(advert_id) REFERENCES adverts (id)
);

CREATE INDEX ix_conversations_owner_id ON conversations (owner_id);

CREATE INDEX ix_conversations_renter_id ON conversations (renter_id);

CREATE INDEX ix_conversations_updated_at ON conversations (updated_at);

CREATE TABLE messages (
	id VARCHAR(36) NOT NULL,
	conversation_id VARCHAR(36) NOT NULL,
	sender_id VARCHAR(36) NOT NULL,
	client_id VARCHAR(64) NOT NULL,
	body VARCHAR(4000) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (conversation_id, sender_id, client_id),
	FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
);

CREATE INDEX ix_message_thread ON messages (conversation_id, created_at);

CREATE INDEX ix_messages_sender_id ON messages (sender_id);

CREATE TABLE listing_aliases (
	old_id VARCHAR(36) NOT NULL,
	listing_id VARCHAR(36) NOT NULL,
	PRIMARY KEY (old_id),
	FOREIGN KEY(old_id) REFERENCES listings (id),
	FOREIGN KEY(listing_id) REFERENCES listings (id)
);

CREATE INDEX ix_listing_aliases_listing_id ON listing_aliases (listing_id);

CREATE TABLE identity_decisions (
	id VARCHAR(36) NOT NULL,
	moderator_id VARCHAR(36) NOT NULL,
	from_listing_id VARCHAR(36) NOT NULL,
	to_listing_id VARCHAR(36) NOT NULL,
	source_ids JSON NOT NULL,
	action VARCHAR(20) NOT NULL,
	reason VARCHAR(1000) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(from_listing_id) REFERENCES listings (id),
	FOREIGN KEY(to_listing_id) REFERENCES listings (id)
);

INSERT INTO schema_migrations(version) VALUES ('004_marketplace_rentals');
COMMIT;
