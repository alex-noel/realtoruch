-- Run as the schema owner after the initial migrations, with psql variables:
-- api_user, auth_user, indexer_user, dataflow_user (IAM names without .gserviceaccount.com).
-- This file intentionally contains no credentials.
\connect rentals
REVOKE ALL ON DATABASE rentals FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE rentals TO :"api_user", :"indexer_user", :"dataflow_user";
GRANT USAGE ON SCHEMA public TO :"api_user", :"indexer_user", :"dataflow_user";
GRANT SELECT ON listings, source_listings, observations, outbox TO :"api_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON favorites, saved_searches, reports TO :"api_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON listings, source_listings, observations, event_receipts, outbox TO :"dataflow_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON listings, source_listings, observations, event_receipts, outbox TO :"indexer_user";
\connect auth
REVOKE ALL ON DATABASE auth FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE auth TO :"auth_user";
GRANT USAGE ON SCHEMA public TO :"auth_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO :"auth_user";
