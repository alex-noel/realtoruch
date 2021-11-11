ALTER TABLE source_poll_state ADD COLUMN next_allowed_request TIMESTAMP WITHOUT TIME ZONE;

CREATE TABLE collection_fetch_state (
    source VARCHAR(40) NOT NULL,
    url_hash VARCHAR(64) NOT NULL,
    source_listing_id VARCHAR(36) NOT NULL REFERENCES source_listings(id) ON DELETE CASCADE,
    validators JSON NOT NULL,
    PRIMARY KEY (source, url_hash)
);
