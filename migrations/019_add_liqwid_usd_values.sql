-- Migration: Add USD value columns to Liqwid APY snapshots
-- Stores USD-converted TVL values at collection time for filtering

-- Add USD value columns
ALTER TABLE liqwid_apy_snapshots
ADD COLUMN IF NOT EXISTS total_supply_usd NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS total_borrows_usd NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS token_price_usd NUMERIC(20, 8);

-- Add index for filtering by USD TVL
CREATE INDEX IF NOT EXISTS idx_liqwid_apy_supply_usd
ON liqwid_apy_snapshots(total_supply_usd DESC)
WHERE total_supply_usd IS NOT NULL;

COMMENT ON COLUMN liqwid_apy_snapshots.total_supply_usd IS 'Total supply value in USD at time of collection';
COMMENT ON COLUMN liqwid_apy_snapshots.total_borrows_usd IS 'Total borrows value in USD at time of collection';
COMMENT ON COLUMN liqwid_apy_snapshots.token_price_usd IS 'Token price in USD at time of collection';
