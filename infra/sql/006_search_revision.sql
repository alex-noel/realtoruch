ALTER TABLE outbox ADD COLUMN last_index_status INTEGER;

-- Separate counters keep older SQLite baseline ORM reads compatible.
CREATE TABLE search_revisions (
    listing_id VARCHAR(36) PRIMARY KEY REFERENCES listings(id),
    revision BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0)
);
INSERT INTO search_revisions (listing_id, revision) SELECT id, 1 FROM listings;
-- Existing documents need a versioned rewrite, including inactive tombstones.
INSERT INTO outbox (id, listing_id, created_at, delivered_at)
SELECT md5('search-revision-006:' || id), id, CURRENT_TIMESTAMP, NULL FROM listings;
