-- Migration 007: Add yield_type column
-- Categorizes yields into: 'lp' (liquidity pool), 'supply' (lending earn), 'borrow' (lending cost)

-- Add yield_type to apr_snapshots (used by Minswap LP data)
ALTER TABLE apr_snapshots 
ADD COLUMN IF NOT EXISTS yield_type VARCHAR(20) DEFAULT 'lp';

-- Add yield_type to kinetic_apy_snapshots (used by Kinetic lending data)
-- Note: Kinetic has both supply and borrow APY in same row, so we track at asset level
ALTER TABLE kinetic_apy_snapshots 
ADD COLUMN IF NOT EXISTS yield_type VARCHAR(20) DEFAULT 'supply';

-- Add yield_type to assets table for reference
ALTER TABLE assets
ADD COLUMN IF NOT EXISTS yield_type VARCHAR(20);

-- Update existing Minswap data to be LP type
UPDATE apr_snapshots SET yield_type = 'lp' WHERE yield_type IS NULL;

-- Update existing Kinetic data to be supply type (primary use case)
UPDATE kinetic_apy_snapshots SET yield_type = 'supply' WHERE yield_type IS NULL;

-- Create indexes for filtering by yield_type
CREATE INDEX IF NOT EXISTS idx_apr_snapshots_yield_type 
ON apr_snapshots(yield_type);

CREATE INDEX IF NOT EXISTS idx_kinetic_apy_yield_type 
ON kinetic_apy_snapshots(yield_type);

-- Add constraint to ensure valid yield_type values
-- Note: Using CHECK constraint for data integrity
ALTER TABLE apr_snapshots 
DROP CONSTRAINT IF EXISTS chk_apr_yield_type;

ALTER TABLE apr_snapshots 
ADD CONSTRAINT chk_apr_yield_type 
CHECK (yield_type IN ('lp', 'supply', 'borrow'));

ALTER TABLE kinetic_apy_snapshots 
DROP CONSTRAINT IF EXISTS chk_kinetic_yield_type;

ALTER TABLE kinetic_apy_snapshots 
ADD CONSTRAINT chk_kinetic_yield_type 
CHECK (yield_type IN ('lp', 'supply', 'borrow'));

COMMENT ON COLUMN apr_snapshots.yield_type IS 
  'Type of yield: lp (liquidity pool), supply (lending earn), borrow (lending cost)';

COMMENT ON COLUMN kinetic_apy_snapshots.yield_type IS 
  'Type of yield: lp (liquidity pool), supply (lending earn), borrow (lending cost)';

COMMENT ON COLUMN assets.yield_type IS 
  'Default yield type for this asset';

