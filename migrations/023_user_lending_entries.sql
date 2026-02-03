-- User Lending Entry Tracking Table
-- Stores the entry date when a lending position is first seen
-- Used for yield calculations

-- ============================================
-- 1. User Lending Entries Table
-- ============================================
CREATE TABLE IF NOT EXISTS user_lending_entries (
    entry_id BIGSERIAL PRIMARY KEY,

    -- User identification
    wallet_address VARCHAR(120) NOT NULL,

    -- Token identification (qToken for Liqwid)
    token_unit VARCHAR(140) NOT NULL,       -- policy_id + asset_name (full unit)

    -- Protocol info
    protocol VARCHAR(50) NOT NULL,          -- 'liqwid'
    market VARCHAR(20) NOT NULL,            -- e.g., 'ADA', 'DJED', 'iUSD'
    position_type VARCHAR(10) NOT NULL,     -- 'supply' or 'borrow'

    -- Entry data
    entry_date DATE NOT NULL,               -- Date position was first received
    entry_tx_hash VARCHAR(66),              -- Transaction hash where token was received

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint: one entry per wallet + token
    UNIQUE(wallet_address, token_unit)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_lending_entries_wallet ON user_lending_entries(wallet_address);
CREATE INDEX IF NOT EXISTS idx_lending_entries_token ON user_lending_entries(token_unit);
CREATE INDEX IF NOT EXISTS idx_lending_entries_protocol ON user_lending_entries(protocol);
CREATE INDEX IF NOT EXISTS idx_lending_entries_wallet_protocol ON user_lending_entries(wallet_address, protocol);

-- Trigger for updated_at
CREATE TRIGGER update_lending_entries_updated_at BEFORE UPDATE ON user_lending_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Comments for documentation
-- ============================================
COMMENT ON TABLE user_lending_entries IS 'Tracks when users first acquired lending tokens (qTokens) for yield calculations';
COMMENT ON COLUMN user_lending_entries.entry_date IS 'Date the lending token was first received by the wallet';
COMMENT ON COLUMN user_lending_entries.token_unit IS 'Full asset unit (policy_id + asset_name hex)';
