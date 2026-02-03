-- Tracked Pools Table
-- Stores pools we're monitoring across protocols.
-- Pools are added when discovered above TVL threshold.
-- Pools are only removed after 7 consecutive days below threshold.

CREATE TABLE IF NOT EXISTS tracked_pools (
    id SERIAL PRIMARY KEY,

    -- Protocol identification
    protocol VARCHAR(50) NOT NULL,          -- 'sundaeswap', 'wingriders', 'minswap'
    pool_identifier VARCHAR(200) NOT NULL,  -- Pool ID or unique identifier

    -- Pool info
    pair_name VARCHAR(100) NOT NULL,        -- e.g., 'iUSD-ADA'
    version VARCHAR(20),                     -- e.g., 'V3', 'V1', 'Stableswaps'

    -- Tracking state
    first_tracked_date DATE NOT NULL DEFAULT CURRENT_DATE,
    last_above_threshold_date DATE,         -- Last date TVL was >= threshold
    consecutive_days_below INT DEFAULT 0,   -- Days consecutively below threshold
    is_active BOOLEAN DEFAULT true,         -- Whether we're still tracking this pool

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(protocol, pool_identifier)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_tracked_pools_protocol ON tracked_pools(protocol);
CREATE INDEX IF NOT EXISTS idx_tracked_pools_active ON tracked_pools(is_active);
CREATE INDEX IF NOT EXISTS idx_tracked_pools_protocol_active ON tracked_pools(protocol, is_active);

-- Trigger for updated_at
CREATE TRIGGER update_tracked_pools_updated_at BEFORE UPDATE ON tracked_pools
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comments
COMMENT ON TABLE tracked_pools IS 'Pools being tracked across DEX protocols with grace period for low TVL';
COMMENT ON COLUMN tracked_pools.consecutive_days_below IS 'Number of consecutive days pool TVL has been below threshold';
COMMENT ON COLUMN tracked_pools.is_active IS 'False after 7 consecutive days below threshold';
