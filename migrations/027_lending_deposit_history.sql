-- Migration: 027_lending_deposit_history.sql
-- Add amount tracking to lending entries (mirrors LP migrations 025/026)
-- and create deposit/withdrawal event log for lending positions.

-- Add qtoken amount tracking columns (mirrors lp_amount in migration 025)
ALTER TABLE user_lending_entries
    ADD COLUMN IF NOT EXISTS qtoken_amount NUMERIC(38, 0);

ALTER TABLE user_lending_entries
    ADD COLUMN IF NOT EXISTS last_amount_check TIMESTAMP WITH TIME ZONE;

ALTER TABLE user_lending_entries
    ADD COLUMN IF NOT EXISTS original_entry_date DATE;

COMMENT ON COLUMN user_lending_entries.qtoken_amount IS
    'Last known qToken quantity from Blockfrost. NULL means pre-migration entry not yet checked.';
COMMENT ON COLUMN user_lending_entries.last_amount_check IS
    'Timestamp of last qToken amount comparison against Blockfrost.';
COMMENT ON COLUMN user_lending_entries.original_entry_date IS
    'True first deposit date, never overwritten. NULL means pre-migration entry.';

-- Lending deposit/withdrawal event log (mirrors user_lp_deposit_history in migration 026)
CREATE TABLE IF NOT EXISTS user_lending_deposit_history (
    id BIGSERIAL PRIMARY KEY,
    wallet_address VARCHAR(120) NOT NULL,
    token_unit VARCHAR(140) NOT NULL,
    event_type VARCHAR(10) NOT NULL CHECK (event_type IN ('deposit', 'withdrawal')),
    qtoken_amount_change NUMERIC(38, 0) NOT NULL,
    qtoken_amount_after NUMERIC(38, 0) NOT NULL,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lending_deposit_history_wallet_token
    ON user_lending_deposit_history (wallet_address, token_unit);
