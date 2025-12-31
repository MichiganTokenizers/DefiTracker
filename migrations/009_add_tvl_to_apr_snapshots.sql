-- Migration 009: Add TVL (Total Value Locked) column to apr_snapshots
-- Tracks the total pooled amount in USD for LP pools
-- For supply/borrow markets, this can represent total supply or total borrowed value

-- Add tvl_usd column to apr_snapshots
ALTER TABLE apr_snapshots 
ADD COLUMN IF NOT EXISTS tvl_usd NUMERIC(20, 2);

-- Create index for TVL-based queries
CREATE INDEX IF NOT EXISTS idx_apr_snapshots_tvl 
ON apr_snapshots(tvl_usd) WHERE tvl_usd IS NOT NULL;

-- Add comment describing the column
COMMENT ON COLUMN apr_snapshots.tvl_usd IS 
  'Total Value Locked in USD - for LPs this is total pooled amount, for lending this is supply/borrow value';

