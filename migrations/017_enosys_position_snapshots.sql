-- Migration: Add Enosys DEX V3 concentrated liquidity position tracking tables
-- Enosys is a Uniswap V3-style DEX on Flare with NFT LP positions and custom price ranges
-- This migration creates tables for tracking pool state and individual LP positions

-- ============================================
-- 1. Enosys Pool Snapshots Table
-- ============================================
-- Stores pool-level metrics for each snapshot period
CREATE TABLE IF NOT EXISTS enosys_pool_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    
    -- Pool identification
    pool_address VARCHAR(66) NOT NULL,       -- Pool contract address
    token0_symbol VARCHAR(20) NOT NULL,      -- First token symbol
    token1_symbol VARCHAR(20) NOT NULL,      -- Second token symbol
    fee_tier INTEGER NOT NULL,               -- Fee tier in basis points (e.g., 500 = 0.05%)
    
    -- Pool state
    current_tick INTEGER,                    -- Current price tick
    sqrt_price_x96 NUMERIC(78, 0),           -- Current sqrt price (Q96 format)
    liquidity NUMERIC(40, 0),                -- Total active liquidity at current tick
    
    -- TVL and volume
    tvl_token0 NUMERIC(30, 8),               -- Total value locked in token0
    tvl_token1 NUMERIC(30, 8),               -- Total value locked in token1  
    tvl_usd NUMERIC(20, 2),                  -- Total value locked in USD
    volume_24h_usd NUMERIC(20, 2),           -- 24h trading volume in USD
    fees_24h_usd NUMERIC(20, 4),             -- 24h fees generated in USD
    
    -- Position counts
    total_positions INTEGER DEFAULT 0,        -- Total NFT positions in this pool
    active_positions INTEGER DEFAULT 0,       -- Positions currently in range
    
    -- Incentives (6-hour epochs)
    epoch_number INTEGER,                    -- Current incentive epoch number
    epoch_incentives NUMERIC(30, 8),         -- Incentive tokens allocated this epoch
    incentive_token_symbol VARCHAR(20),      -- Symbol of incentive token (e.g., WFLR)
    
    -- Timestamps
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint for time-series data
    CONSTRAINT enosys_pool_unique_snapshot UNIQUE (pool_address, timestamp)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_enosys_pool_timestamp ON enosys_pool_snapshots(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_enosys_pool_address ON enosys_pool_snapshots(pool_address, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_enosys_pool_pair ON enosys_pool_snapshots(token0_symbol, token1_symbol, timestamp DESC);

-- ============================================
-- 2. Enosys Position Snapshots Table
-- ============================================
-- Stores individual NFT LP position data with range analysis
CREATE TABLE IF NOT EXISTS enosys_position_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    
    -- Position identification
    token_id BIGINT NOT NULL,                -- NFT token ID
    owner_address VARCHAR(66),               -- Position owner wallet address
    pool_address VARCHAR(66) NOT NULL,       -- Pool this position belongs to
    
    -- Position range (tick bounds)
    tick_lower INTEGER NOT NULL,             -- Lower tick bound
    tick_upper INTEGER NOT NULL,             -- Upper tick bound
    
    -- Range analysis
    range_width_ticks INTEGER,               -- tick_upper - tick_lower
    range_width_percent NUMERIC(10, 4),      -- Range width as percentage of price
    range_category VARCHAR(20),              -- 'narrow' (<1%), 'medium' (1-5%), 'wide' (>5%)
    
    -- Position state
    liquidity NUMERIC(40, 0),                -- Position liquidity amount
    is_in_range BOOLEAN,                     -- Whether current price is within position range
    
    -- Token amounts
    amount0 NUMERIC(30, 8),                  -- Current amount of token0 in position
    amount1 NUMERIC(30, 8),                  -- Current amount of token1 in position
    amount_usd NUMERIC(20, 2),               -- Total position value in USD
    
    -- Fees earned (uncollected)
    fees_token0 NUMERIC(30, 8),              -- Uncollected fees in token0
    fees_token1 NUMERIC(30, 8),              -- Uncollected fees in token1
    fees_usd NUMERIC(20, 4),                 -- Uncollected fees in USD
    
    -- Fee/incentive metrics (for APR calculation)
    fees_24h_usd NUMERIC(20, 4),             -- Fees earned in last 24h (estimated)
    fee_apr NUMERIC(10, 4),                  -- Annualized fee APR for this position
    
    -- Epoch incentive tracking
    epoch_number INTEGER,                    -- Current epoch at snapshot time
    time_in_range_pct NUMERIC(6, 2),         -- % of epoch this position was in range
    incentive_share NUMERIC(30, 8),          -- Share of epoch incentives earned
    incentive_apr NUMERIC(10, 4),            -- Annualized incentive APR
    
    -- Total APR
    total_apr NUMERIC(10, 4),                -- fee_apr + incentive_apr
    
    -- Reference to pool snapshot
    pool_snapshot_id INTEGER REFERENCES enosys_pool_snapshots(snapshot_id),
    
    -- Timestamps
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint
    CONSTRAINT enosys_position_unique_snapshot UNIQUE (token_id, timestamp)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_enosys_pos_timestamp ON enosys_position_snapshots(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_enosys_pos_token_id ON enosys_position_snapshots(token_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_enosys_pos_pool ON enosys_position_snapshots(pool_address, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_enosys_pos_owner ON enosys_position_snapshots(owner_address, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_enosys_pos_range_cat ON enosys_position_snapshots(range_category, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_enosys_pos_in_range ON enosys_position_snapshots(is_in_range, timestamp DESC);

-- ============================================
-- 3. Range Analysis Aggregation View
-- ============================================
-- Provides summary statistics by range category for analysis
CREATE OR REPLACE VIEW enosys_range_analysis AS
SELECT 
    pool_address,
    range_category,
    DATE_TRUNC('day', timestamp) as snapshot_date,
    COUNT(*) as position_count,
    AVG(range_width_percent) as avg_range_width_pct,
    SUM(CASE WHEN is_in_range THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100 as pct_in_range,
    AVG(fee_apr) as avg_fee_apr,
    AVG(incentive_apr) as avg_incentive_apr,
    AVG(total_apr) as avg_total_apr,
    SUM(amount_usd) as total_tvl_usd,
    SUM(fees_24h_usd) as total_fees_24h_usd
FROM enosys_position_snapshots
GROUP BY pool_address, range_category, DATE_TRUNC('day', timestamp);

-- ============================================
-- 4. Convert to TimescaleDB hypertables
-- ============================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        -- Pool snapshots hypertable
        PERFORM create_hypertable(
            'enosys_pool_snapshots', 
            'timestamp',
            if_not_exists => TRUE,
            migrate_data => TRUE
        );
        RAISE NOTICE 'Created hypertable for enosys_pool_snapshots';
        
        -- Position snapshots hypertable
        PERFORM create_hypertable(
            'enosys_position_snapshots', 
            'timestamp',
            if_not_exists => TRUE,
            migrate_data => TRUE
        );
        RAISE NOTICE 'Created hypertable for enosys_position_snapshots';
    ELSE
        RAISE NOTICE 'TimescaleDB not installed, using regular tables';
    END IF;
EXCEPTION
    WHEN others THEN
        RAISE NOTICE 'Could not create hypertables: %', SQLERRM;
END;
$$;

-- ============================================
-- 5. Table and Column Comments
-- ============================================
COMMENT ON TABLE enosys_pool_snapshots IS 'Historical snapshots of Enosys DEX V3 pool state and metrics';
COMMENT ON COLUMN enosys_pool_snapshots.current_tick IS 'Current price tick - positions in range if tick_lower <= current_tick < tick_upper';
COMMENT ON COLUMN enosys_pool_snapshots.fee_tier IS 'Pool fee tier in basis points (100 = 0.01%, 500 = 0.05%, 3000 = 0.3%)';
COMMENT ON COLUMN enosys_pool_snapshots.epoch_number IS 'Enosys uses 6-hour epochs for incentive distribution';

COMMENT ON TABLE enosys_position_snapshots IS 'Historical snapshots of individual NFT LP positions with range analysis';
COMMENT ON COLUMN enosys_position_snapshots.tick_lower IS 'Lower price tick bound - position provides liquidity above this price';
COMMENT ON COLUMN enosys_position_snapshots.tick_upper IS 'Upper price tick bound - position provides liquidity below this price';
COMMENT ON COLUMN enosys_position_snapshots.range_category IS 'Classification: narrow (<1% width), medium (1-5%), wide (>5%)';
COMMENT ON COLUMN enosys_position_snapshots.is_in_range IS 'True if current pool tick is within position tick bounds';
COMMENT ON COLUMN enosys_position_snapshots.time_in_range_pct IS 'Percentage of epoch time this position was in range (for incentive calc)';
COMMENT ON COLUMN enosys_position_snapshots.fee_apr IS 'Annualized APR from trading fees for this position';
COMMENT ON COLUMN enosys_position_snapshots.incentive_apr IS 'Annualized APR from epoch incentives for this position';

