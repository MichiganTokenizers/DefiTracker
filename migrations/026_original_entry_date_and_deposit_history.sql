-- Migration: 026_original_entry_date_and_deposit_history.sql
-- Preserve the actual first deposit date separately from the weighted
-- calculation date, and track deposit/withdrawal events for display.

-- Add original_entry_date: the true first deposit date, never overwritten.
-- NULL means pre-migration entry that needs recovery via Blockfrost scan.
ALTER TABLE user_lp_entries
    ADD COLUMN IF NOT EXISTS original_entry_date DATE;

-- Deposit/withdrawal event log for portfolio tooltip display
CREATE TABLE IF NOT EXISTS user_lp_deposit_history (
    id BIGSERIAL PRIMARY KEY,
    wallet_address VARCHAR(120) NOT NULL,
    policy_id VARCHAR(66) NOT NULL,
    asset_name VARCHAR(128) NOT NULL,
    event_type VARCHAR(10) NOT NULL CHECK (event_type IN ('deposit', 'withdrawal')),
    lp_amount_change NUMERIC(38, 0) NOT NULL,
    lp_amount_after NUMERIC(38, 0) NOT NULL,
    price_ratio_at_event NUMERIC(20, 10),
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lp_deposit_history_wallet_token
    ON user_lp_deposit_history (wallet_address, policy_id, asset_name);
