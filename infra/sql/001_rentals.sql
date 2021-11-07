-- Initial schema. Apply once in the indicated database as the schema owner.

BEGIN;


CREATE TABLE event_receipts (
	id VARCHAR(64) NOT NULL,
	received_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
)

;


CREATE TABLE listings (
	id VARCHAR(36) NOT NULL,
	title VARCHAR(240) NOT NULL,
	description TEXT NOT NULL,
	city VARCHAR(100) NOT NULL,
	district VARCHAR(100) NOT NULL,
	region VARCHAR(100) NOT NULL,
	address VARCHAR(240) NOT NULL,
	lat FLOAT,
	lon FLOAT,
	area_m2 FLOAT NOT NULL,
	rooms INTEGER NOT NULL,
	floor INTEGER,
	rent_pln INTEGER NOT NULL,
	fees_pln INTEGER,
	deposit_pln INTEGER,
	commission_pln INTEGER,
	advertiser_type VARCHAR(20) NOT NULL,
	property_type VARCHAR(30) NOT NULL,
	status VARCHAR(20) NOT NULL,
	amenities JSON NOT NULL,
	images JSON NOT NULL,
	risk_flags JSON NOT NULL,
	risk_score INTEGER NOT NULL,
	is_demo BOOLEAN NOT NULL,
	first_seen TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	last_seen TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_listings_last_seen ON listings (last_seen);

CREATE INDEX ix_listings_rent_pln ON listings (rent_pln);

CREATE INDEX ix_listings_status ON listings (status);

CREATE INDEX ix_listings_region ON listings (region);

CREATE INDEX ix_listings_district ON listings (district);

CREATE INDEX ix_listings_city ON listings (city);


CREATE TABLE saved_searches (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	name VARCHAR(100) NOT NULL,
	filters JSON NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_saved_searches_user_id ON saved_searches (user_id);


CREATE TABLE favorites (
	user_id VARCHAR(36) NOT NULL,
	listing_id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (user_id, listing_id),
	FOREIGN KEY(listing_id) REFERENCES listings (id)
)

;


CREATE TABLE outbox (
	id VARCHAR(36) NOT NULL,
	listing_id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	delivered_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(listing_id) REFERENCES listings (id)
)

;

CREATE INDEX ix_outbox_listing_id ON outbox (listing_id);


CREATE TABLE reports (
	id VARCHAR(36) NOT NULL,
	listing_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	reason VARCHAR(1000) NOT NULL,
	status VARCHAR(20) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(listing_id) REFERENCES listings (id)
)

;


CREATE TABLE source_listings (
	id VARCHAR(36) NOT NULL,
	listing_id VARCHAR(36) NOT NULL,
	source VARCHAR(40) NOT NULL,
	external_id VARCHAR(200) NOT NULL,
	url TEXT NOT NULL,
	phone_hash VARCHAR(64),
	data JSON NOT NULL,
	status VARCHAR(20) NOT NULL,
	observed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	match_reason TEXT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (source, external_id),
	FOREIGN KEY(listing_id) REFERENCES listings (id)
)

;

CREATE INDEX ix_source_listings_phone_hash ON source_listings (phone_hash);

CREATE INDEX ix_source_listings_listing_id ON source_listings (listing_id);


CREATE TABLE observations (
	id VARCHAR(36) NOT NULL,
	listing_id VARCHAR(36) NOT NULL,
	source_listing_id VARCHAR(36) NOT NULL,
	observed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	rent_pln INTEGER NOT NULL,
	fees_pln INTEGER,
	status VARCHAR(20) NOT NULL,
	changed BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (source_listing_id, observed_at),
	FOREIGN KEY(listing_id) REFERENCES listings (id),
	FOREIGN KEY(source_listing_id) REFERENCES source_listings (id)
)

;

CREATE INDEX ix_obs_listing_time ON observations (listing_id, observed_at);

CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(50) PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP);

INSERT INTO schema_migrations(version) VALUES ('001_rentals');

CREATE INDEX ix_listing_match_candidates ON listings (city, rooms, area_m2);

COMMIT;
