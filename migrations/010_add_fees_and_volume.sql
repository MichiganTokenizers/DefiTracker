-- Migration 010: Add fees and volume tracking columns
-- For DEX (Minswap): trading_fee_24h and volume_24h from API
-- For Lending (Liqwid, Kinetic): Calculated daily interest

-- Add columns to apr_snapshots (used by Minswap)
ALTER TABLE apr_snapshots 
ADD COLUMN IF NOT EXISTS fees_24h NUMERIC(20, 2);

ALTER TABLE apr_snapshots 
ADD COLUMN IF NOT EXISTS volume_24h NUMERIC(20, 2);

-- Add daily_interest_usd to liqwid_apy_snapshots
-- Represents approximate daily interest earned by suppliers
ALTER TABLE liqwid_apy_snapshots
ADD COLUMN IF NOT EXISTS daily_interest_usd NUMERIC(20, 2);

-- Add daily_interest_usd to kinetic_apy_snapshots
ALTER TABLE kinetic_apy_snapshots
ADD COLUMN IF NOT EXISTS daily_interest_usd NUMERIC(20, 2);

-- Add comments
COMMENT ON COLUMN apr_snapshots.fees_24h IS 
  'Trading fees generated in last 24 hours (USD) - for DEX pools';

COMMENT ON COLUMN apr_snapshots.volume_24h IS 
  'Trading volume in last 24 hours (USD) - for DEX pools';

COMMENT ON COLUMN liqwid_apy_snapshots.daily_interest_usd IS 
  'Approximate daily interest from borrows (borrow_apy * total_borrows / 365)';

COMMENT ON COLUMN kinetic_apy_snapshots.daily_interest_usd IS 
  'Approximate daily interest from borrows (borrow_apy * total_borrows / 365)';

