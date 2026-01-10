-- Add APR breakdown columns to apr_snapshots table
-- These columns store the individual components that make up the total APR:
--   fee_apr: Trading fee APR (from swap fees)
--   staking_apr: Staking rewards APR (e.g., WingRiders embedded ADA staking)
--   farm_apr: Farm/yield farming rewards APR (token emissions)

ALTER TABLE apr_snapshots ADD COLUMN IF NOT EXISTS fee_apr NUMERIC(10, 4);
ALTER TABLE apr_snapshots ADD COLUMN IF NOT EXISTS staking_apr NUMERIC(10, 4);
ALTER TABLE apr_snapshots ADD COLUMN IF NOT EXISTS farm_apr NUMERIC(10, 4);

-- Add comment for documentation
COMMENT ON COLUMN apr_snapshots.fee_apr IS 'Trading fee APR component';
COMMENT ON COLUMN apr_snapshots.staking_apr IS 'Staking rewards APR component (e.g., embedded ADA staking)';
COMMENT ON COLUMN apr_snapshots.farm_apr IS 'Farm/yield farming rewards APR component';

