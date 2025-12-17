-- Kinetic Protocol APY Snapshots
-- Stores historical APY data for Kinetic lending markets

-- ============================================
-- 1. Kinetic APY Snapshots Table
-- ============================================
CREATE TABLE IF NOT EXISTS kinetic_apy_snapshots (
    snapshot_id BIGSERIAL,
    asset_id INTEGER NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    
    -- Supply side APY
    supply_apy NUMERIC(10, 4),              -- Interest rate for suppliers (e.g., 4.89 for 4.89%)
    supply_distribution_apy NUMERIC(10, 4), -- rFLR/WFLR reward APY for supplying
    total_supply_apy NUMERIC(10, 4),        -- supply_apy + supply_distribution_apy
    
    -- Borrow side APY
    borrow_apy NUMERIC(10, 4),              -- Interest rate paid by borrowers
    borrow_distribution_apy NUMERIC(10, 4), -- Reward APY for borrowing (if any, usually NULL)
    
    -- Market data (optional, for context)
    total_supply_tokens NUMERIC(30, 8),     -- Total tokens supplied to market
    total_borrowed_tokens NUMERIC(30, 8),   -- Total tokens borrowed from market
    utilization_rate NUMERIC(10, 4),        -- Borrowed / Supplied as percentage
    
    -- Price reference
    price_snapshot_id BIGINT,               -- FK to price_snapshots used for calculation
    
    -- Timestamps
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (snapshot_id, timestamp)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_kinetic_apy_timestamp ON kinetic_apy_snapshots(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_kinetic_apy_asset ON kinetic_apy_snapshots(asset_id);
CREATE INDEX IF NOT EXISTS idx_kinetic_apy_asset_timestamp ON kinetic_apy_snapshots(asset_id, timestamp DESC);

-- Convert to TimescaleDB hypertable (run after table creation)
-- SELECT create_hypertable('kinetic_apy_snapshots', 'timestamp', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);

-- ============================================
-- Comments for documentation
-- ============================================
COMMENT ON TABLE kinetic_apy_snapshots IS 'Historical APY snapshots for Kinetic protocol lending markets';
COMMENT ON COLUMN kinetic_apy_snapshots.supply_apy IS 'Interest rate APY earned by suppliers';
COMMENT ON COLUMN kinetic_apy_snapshots.supply_distribution_apy IS 'rFLR/WFLR reward APY for supplying';
COMMENT ON COLUMN kinetic_apy_snapshots.total_supply_apy IS 'Total APY for suppliers (supply + distribution)';
COMMENT ON COLUMN kinetic_apy_snapshots.borrow_apy IS 'Interest rate APY paid by borrowers';
COMMENT ON COLUMN kinetic_apy_snapshots.borrow_distribution_apy IS 'Reward APY for borrowers (if any)';
COMMENT ON COLUMN kinetic_apy_snapshots.utilization_rate IS 'Market utilization rate (borrowed/supplied)';

