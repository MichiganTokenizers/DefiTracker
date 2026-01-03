-- Add version column to apr_snapshots for LP pool versioning
-- Used by DEXs like SundaeSwap (V1, V3) and WingRiders (V1, V2)

ALTER TABLE apr_snapshots
ADD COLUMN IF NOT EXISTS version VARCHAR(10);

COMMENT ON COLUMN apr_snapshots.version IS 'Protocol version for LP pools (e.g., V1, V3 for SundaeSwap)';

-- Create index for filtering by version
CREATE INDEX IF NOT EXISTS idx_apr_snapshots_version ON apr_snapshots(version);

