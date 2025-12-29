-- Migration: Add Liqwid APY snapshots table
-- Liqwid Finance is a lending protocol on Cardano, similar to Kinetic on Flare
-- This table stores historical supply and borrow APY data for Liqwid markets

-- Create Liqwid APY snapshots table
CREATE TABLE IF NOT EXISTS liqwid_apy_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES assets(asset_id),
    
    -- Market identification
    market_id VARCHAR(100),          -- Liqwid market identifier
    
    -- Supply side APY (what lenders earn)
    supply_apy NUMERIC(10, 4),       -- Base supply APY percentage
    lq_supply_apy NUMERIC(10, 4),    -- LQ token reward APY percentage
    total_supply_apy NUMERIC(10, 4), -- Total supply APY (base + LQ rewards)
    
    -- Borrow side APY (what borrowers pay)
    borrow_apy NUMERIC(10, 4),       -- Base borrow APY percentage
    
    -- Market state data
    total_supply NUMERIC(30, 6),     -- Total tokens supplied (in token units)
    total_borrows NUMERIC(30, 6),    -- Total tokens borrowed (in token units)
    utilization_rate NUMERIC(10, 6), -- Utilization rate (0-1 scale)
    available_liquidity NUMERIC(30, 6), -- Available liquidity for borrowing
    
    -- Yield type (supply or borrow - lending markets have both)
    yield_type VARCHAR(20) DEFAULT 'supply',
    
    -- Timestamp
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Index for time-series queries
    CONSTRAINT liqwid_apy_asset_time UNIQUE (asset_id, market_id, timestamp)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_liqwid_apy_timestamp ON liqwid_apy_snapshots(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_liqwid_apy_asset ON liqwid_apy_snapshots(asset_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_liqwid_apy_market ON liqwid_apy_snapshots(market_id, timestamp DESC);

-- Convert to TimescaleDB hypertable for efficient time-series storage
-- This will only run if TimescaleDB extension is available
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'liqwid_apy_snapshots', 
            'timestamp',
            if_not_exists => TRUE,
            migrate_data => TRUE
        );
        RAISE NOTICE 'Created hypertable for liqwid_apy_snapshots';
    ELSE
        RAISE NOTICE 'TimescaleDB not installed, using regular table';
    END IF;
EXCEPTION
    WHEN others THEN
        RAISE NOTICE 'Could not create hypertable: %', SQLERRM;
END;
$$;

-- Add comment describing the table
COMMENT ON TABLE liqwid_apy_snapshots IS 'Historical APY snapshots for Liqwid Finance lending markets on Cardano';
COMMENT ON COLUMN liqwid_apy_snapshots.supply_apy IS 'Base supply APY percentage (e.g., 5.25 for 5.25%)';
COMMENT ON COLUMN liqwid_apy_snapshots.lq_supply_apy IS 'LQ token reward APY percentage (additional yield from LQ tokens)';
COMMENT ON COLUMN liqwid_apy_snapshots.total_supply_apy IS 'Total supply APY (base + LQ rewards)';
COMMENT ON COLUMN liqwid_apy_snapshots.borrow_apy IS 'Borrow APY percentage (e.g., 8.75 for 8.75%)';
COMMENT ON COLUMN liqwid_apy_snapshots.utilization_rate IS 'Market utilization rate (0-1 scale, e.g., 0.75 for 75%)';

