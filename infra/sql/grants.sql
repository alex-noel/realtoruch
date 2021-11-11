-- Run as the schema owner after the initial migrations, with psql variables:
-- api_user, auth_user, indexer_user, alerts_user, dataflow_user (IAM names without .gserviceaccount.com).
-- This file intentionally contains no credentials.
\connect rentals
REVOKE ALL ON DATABASE rentals FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE rentals TO :"api_user", :"indexer_user", :"alerts_user", :"dataflow_user";
GRANT USAGE ON SCHEMA public TO :"api_user", :"indexer_user", :"alerts_user", :"dataflow_user";
GRANT SELECT ON listings, source_listings, observations, outbox TO :"api_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON favorites, saved_searches, reports TO :"api_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON seen_prices, search_matches, push_subscriptions TO :"api_user";
GRANT SELECT, UPDATE ON notifications TO :"api_user";
GRANT SELECT, INSERT, UPDATE ON email_subscriptions, email_deliveries TO :"api_user";
GRANT SELECT ON listings, source_listings, saved_searches, seen_prices TO :"alerts_user";
GRANT SELECT, UPDATE ON favorites, push_subscriptions TO :"alerts_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON search_matches, notifications, push_deliveries, alert_events TO :"alerts_user";
GRANT SELECT ON email_subscriptions TO :"alerts_user";
GRANT SELECT, INSERT, UPDATE ON email_deliveries TO :"alerts_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON listings, source_listings, observations, event_receipts, outbox TO :"dataflow_user";
GRANT SELECT, INSERT ON alert_events TO :"dataflow_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON listings, source_listings, observations, event_receipts, outbox TO :"indexer_user";
GRANT SELECT, INSERT, DELETE ON alert_events TO :"indexer_user";
\connect auth
REVOKE ALL ON DATABASE auth FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE auth TO :"auth_user";
GRANT USAGE ON SCHEMA public TO :"auth_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO :"auth_user";
