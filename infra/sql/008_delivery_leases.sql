ALTER TABLE email_deliveries ADD COLUMN claim_token VARCHAR(64);
ALTER TABLE push_deliveries ADD COLUMN claim_token VARCHAR(64);
