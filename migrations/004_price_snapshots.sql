-- Price Snapshots Table
-- Stores historical token price data from various sources (DEX, oracles)
-- Reusable across all protocols

-- ============================================
-- 1. Price Snapshots Table
-- ============================================
CREATE TABLE IF NOT EXISTS price_snapshots (
    snapshot_id BIGSERIAL,
    
    -- Token identification
    token_symbol VARCHAR(20) NOT NULL,      -- e.g., 'WFLR', 'FXRP', 'USDT0'
    token_address VARCHAR(66),              -- Contract address (NULL for native tokens)
    
    -- Price in USD (if available)
    price_usd NUMERIC(20, 8),               -- Price in USD
    
    -- Price in another token (for DEX pairs)
    quote_token_symbol VARCHAR(20),         -- What token it's priced in (e.g., 'USDT0')
    quote_token_address VARCHAR(66),        -- Quote token contract address
    price_in_quote NUMERIC(20, 8),          -- Price in quote token
    
    -- Source information
    source VARCHAR(50) NOT NULL,            -- e.g., 'blazeswap', 'chainlink', 'coingecko'
    pair_address VARCHAR(66),               -- DEX pair contract used (if applicable)
    
    -- Liquidity info (for DEX sources)
    reserve_token NUMERIC(30, 8),           -- Reserve of token in pair
    reserve_quote NUMERIC(30, 8),           -- Reserve of quote token in pair
    
    -- Timestamps
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (snapshot_id, timestamp)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_price_timestamp ON price_snapshots(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_price_token ON price_snapshots(token_symbol);
CREATE INDEX IF NOT EXISTS idx_price_source ON price_snapshots(source);
CREATE INDEX IF NOT EXISTS idx_price_token_timestamp ON price_snapshots(token_symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_price_token_source_timestamp ON price_snapshots(token_symbol, source, timestamp DESC);

-- Convert to TimescaleDB hypertable (run after table creation)
-- SELECT create_hypertable('price_snapshots', 'timestamp', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);

-- ============================================
-- Add foreign key to kinetic_apy_snapshots
-- ============================================
-- Note: This requires price_snapshots to exist first
-- ALTER TABLE kinetic_apy_snapshots 
--     ADD CONSTRAINT fk_kinetic_price_snapshot 
--     FOREIGN KEY (price_snapshot_id, timestamp) 
--     REFERENCES price_snapshots(snapshot_id, timestamp);

-- ============================================
-- Comments for documentation
-- ============================================
COMMENT ON TABLE price_snapshots IS 'Historical token price data from DEX and oracle sources';
COMMENT ON COLUMN price_snapshots.token_symbol IS 'Token symbol (e.g., WFLR, FXRP)';
COMMENT ON COLUMN price_snapshots.price_usd IS 'Price in USD (may be NULL if not available)';
COMMENT ON COLUMN price_snapshots.quote_token_symbol IS 'Token used for pricing (e.g., USDT0)';
COMMENT ON COLUMN price_snapshots.price_in_quote IS 'Price in quote token';
COMMENT ON COLUMN price_snapshots.source IS 'Price source (blazeswap, chainlink, etc.)';
COMMENT ON COLUMN price_snapshots.pair_address IS 'DEX pair contract address used';

