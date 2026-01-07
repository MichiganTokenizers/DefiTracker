-- Migration 013: Add 1-day APR column
-- For Minswap: Store both 30-day rolling average (apr) and calculated 1-day APR (apr_1d)
-- apr_1d = (trading_fee_24h / liquidity) * 365 * 100
-- This provides a more volatile but accurate daily snapshot vs the smoothed 30-day average

-- Add apr_1d column to apr_snapshots
ALTER TABLE apr_snapshots 
ADD COLUMN IF NOT EXISTS apr_1d NUMERIC(20, 8);

-- Add comment
COMMENT ON COLUMN apr_snapshots.apr_1d IS 
  'Calculated 1-day APR from trading_fee_24h / TVL * 365 * 100. More volatile than apr (30-day avg).';

