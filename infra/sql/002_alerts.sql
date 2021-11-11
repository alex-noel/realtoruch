-- Apply after 001_rentals.sql, as schema owner, before starting the alerts service.

BEGIN;

ALTER TABLE favorites ADD COLUMN price_floor INTEGER;

ALTER TABLE saved_searches ADD COLUMN city_key VARCHAR(100) NOT NULL DEFAULT '';

UPDATE favorites f SET price_floor = l.rent_pln FROM listings l WHERE l.id = f.listing_id;

UPDATE saved_searches SET city_key = translate(lower(trim(coalesce(filters->>'city', ''))), 'ąćęłńóśźż', 'acelnoszz');

CREATE INDEX ix_saved_searches_city_key ON saved_searches (city_key);

CREATE INDEX ix_source_recheck ON source_listings (source, status, observed_at);

CREATE INDEX ix_source_lookup ON source_listings (source, url);

CREATE INDEX ix_outbox_pending ON outbox (delivered_at, created_at);

CREATE TABLE push_subscriptions (
	id VARCHAR(64) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	kind VARCHAR(10) NOT NULL,
	data JSON NOT NULL,
	active BOOLEAN NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE INDEX ix_push_subscriptions_user_id ON push_subscriptions (user_id);

CREATE TABLE alert_events (
	id VARCHAR(36) NOT NULL,
	listing_id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	processed_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(listing_id) REFERENCES listings (id)
);

CREATE INDEX ix_alert_events_processed_at ON alert_events (processed_at);

CREATE INDEX ix_alert_events_listing_id ON alert_events (listing_id);

CREATE TABLE notifications (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	listing_id VARCHAR(36) NOT NULL,
	search_id VARCHAR(36),
	dedupe_key VARCHAR(64) NOT NULL,
	kind VARCHAR(30) NOT NULL,
	title VARCHAR(240) NOT NULL,
	rent_pln INTEGER NOT NULL,
	previous_rent_pln INTEGER,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	read_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(listing_id) REFERENCES listings (id),
	FOREIGN KEY(search_id) REFERENCES saved_searches (id) ON DELETE SET NULL,
	UNIQUE (dedupe_key)
);

CREATE INDEX ix_notification_inbox ON notifications (user_id, created_at);

CREATE TABLE search_matches (
	search_id VARCHAR(36) NOT NULL,
	listing_id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (search_id, listing_id),
	FOREIGN KEY(search_id) REFERENCES saved_searches (id) ON DELETE CASCADE,
	FOREIGN KEY(listing_id) REFERENCES listings (id)
);

CREATE TABLE seen_prices (
	user_id VARCHAR(36) NOT NULL,
	listing_id VARCHAR(36) NOT NULL,
	rent_pln INTEGER NOT NULL,
	seen_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (user_id, listing_id, rent_pln),
	FOREIGN KEY(listing_id) REFERENCES listings (id)
);

CREATE TABLE push_deliveries (
	id VARCHAR(36) NOT NULL,
	notification_id VARCHAR(36) NOT NULL,
	subscription_id VARCHAR(64) NOT NULL,
	status VARCHAR(20) NOT NULL,
	attempts INTEGER NOT NULL,
	next_attempt_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	lease_until TIMESTAMP WITHOUT TIME ZONE,
	receipt_id VARCHAR(100),
	last_error VARCHAR(100),
	delivered_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (notification_id, subscription_id),
	FOREIGN KEY(notification_id) REFERENCES notifications (id),
	FOREIGN KEY(subscription_id) REFERENCES push_subscriptions (id)
);

CREATE INDEX ix_push_due ON push_deliveries (status, next_attempt_at);

INSERT INTO schema_migrations(version) VALUES ('002_alerts');

COMMIT;

-- For an existing catalog, run the baseline-searches worker command once before starting alerts.
