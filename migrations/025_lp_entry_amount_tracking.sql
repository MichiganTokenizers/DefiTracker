-- Migration: 025_lp_entry_amount_tracking.sql
-- Track LP token amounts for detecting deposits/withdrawals
-- Enables weighted-average entry_date and entry_price_ratio adjustments
-- when users add to existing LP positions.

ALTER TABLE user_lp_entries
    ADD COLUMN IF NOT EXISTS lp_amount NUMERIC(38, 0);

ALTER TABLE user_lp_entries
    ADD COLUMN IF NOT EXISTS last_amount_check TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN user_lp_entries.lp_amount IS
    'Last known LP token quantity from Blockfrost. NULL means pre-migration entry not yet checked.';
COMMENT ON COLUMN user_lp_entries.last_amount_check IS
    'Timestamp of last LP amount comparison against Blockfrost.';
