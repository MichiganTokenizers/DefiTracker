-- Add swap fee percentage column to apr_snapshots table
-- This stores the trading fee charged per swap (e.g., 0.30 for 0.30%)

ALTER TABLE apr_snapshots ADD COLUMN IF NOT EXISTS swap_fee_percent NUMERIC(6, 4);

COMMENT ON COLUMN apr_snapshots.swap_fee_percent IS 'Swap/trading fee percentage (e.g., 0.30 for 0.30%)';

