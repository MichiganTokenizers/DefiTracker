-- User LP Entry Tracking Table
-- Stores the entry date and price ratio when an LP position is first seen
-- Used for impermanent loss calculations

-- ============================================
-- 1. User LP Entries Table
-- ============================================
CREATE TABLE IF NOT EXISTS user_lp_entries (
    entry_id BIGSERIAL PRIMARY KEY,

    -- User identification
    wallet_address VARCHAR(120) NOT NULL,

    -- LP token identification
    policy_id VARCHAR(66) NOT NULL,
    asset_name VARCHAR(128) NOT NULL,      -- Hex-encoded asset name

    -- Protocol info
    protocol VARCHAR(50) NOT NULL,          -- 'minswap', 'sundaeswap', 'wingriders'
    pool_name VARCHAR(100),                 -- e.g., 'NIGHT/ADA'

    -- Entry data
    entry_date DATE NOT NULL,               -- Date position was first received
    entry_tx_hash VARCHAR(66),              -- Transaction hash where LP was received

    -- Price ratio at entry (Token A / Token B based on pool reserves)
    entry_price_ratio NUMERIC(20, 10),      -- reserve_A / reserve_B at entry

    -- Token info for reference
    token_a_symbol VARCHAR(20),
    token_b_symbol VARCHAR(20),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint: one entry per wallet + LP token
    UNIQUE(wallet_address, policy_id, asset_name)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_lp_entries_wallet ON user_lp_entries(wallet_address);
CREATE INDEX IF NOT EXISTS idx_lp_entries_lp_token ON user_lp_entries(policy_id, asset_name);
CREATE INDEX IF NOT EXISTS idx_lp_entries_protocol ON user_lp_entries(protocol);
CREATE INDEX IF NOT EXISTS idx_lp_entries_wallet_protocol ON user_lp_entries(wallet_address, protocol);

-- Trigger for updated_at
CREATE TRIGGER update_lp_entries_updated_at BEFORE UPDATE ON user_lp_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Comments for documentation
-- ============================================
COMMENT ON TABLE user_lp_entries IS 'Tracks when users first acquired LP tokens for IL calculations';
COMMENT ON COLUMN user_lp_entries.entry_price_ratio IS 'Token A / Token B price ratio from pool reserves at entry';
COMMENT ON COLUMN user_lp_entries.entry_date IS 'Date the LP token was first received by the wallet';
