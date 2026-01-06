-- User Accounts Schema
-- Migration: 012_user_accounts.sql
-- Adds user authentication (email/password and Cardano wallet) and saved charts

-- ============================================
-- 1. Users Table
-- ============================================
-- Supports both wallet and email auth
-- NOTE: Wallet users can optionally add an email later for notifications/recovery

CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    
    -- Authentication method tracking
    auth_method VARCHAR(20) NOT NULL,  -- 'email' or 'wallet' (how they first registered)
    
    -- Email authentication (required for email users, optional for wallet users)
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),        -- Only set for email-registered users
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(128),
    reset_token VARCHAR(128),
    reset_token_expires TIMESTAMP WITH TIME ZONE,
    
    -- Wallet authentication (required for wallet users)
    wallet_address VARCHAR(128) UNIQUE,  -- Cardano bech32 address (addr1...)
    
    -- Metadata
    display_name VARCHAR(100),         -- Optional friendly name
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Ensure at least one auth method is present
    CONSTRAINT valid_auth CHECK (
        (auth_method = 'email' AND email IS NOT NULL AND password_hash IS NOT NULL) OR
        (auth_method = 'wallet' AND wallet_address IS NOT NULL)
    )
);

-- Indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_wallet ON users(wallet_address) WHERE wallet_address IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_verification_token ON users(verification_token) WHERE verification_token IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_reset_token ON users(reset_token) WHERE reset_token IS NOT NULL;

-- Trigger for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 2. Saved Charts Table
-- ============================================
-- Stores user's saved chart configurations

CREATE TABLE IF NOT EXISTS saved_charts (
    chart_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    filters JSONB NOT NULL,        -- {chain, protocol, assets[], yield_type, days}
    display_options JSONB,         -- {colors{}, comparison_mode, etc.}
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_saved_charts_user ON saved_charts(user_id);

-- Trigger for updated_at
CREATE TRIGGER update_saved_charts_updated_at BEFORE UPDATE ON saved_charts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 3. Wallet Challenge Nonces (for secure login)
-- ============================================
-- Temporary storage for wallet authentication challenges

CREATE TABLE IF NOT EXISTS wallet_challenges (
    challenge_id SERIAL PRIMARY KEY,
    wallet_address VARCHAR(128) NOT NULL,
    nonce VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '5 minutes'
);

-- Index for lookup and cleanup
CREATE INDEX IF NOT EXISTS idx_wallet_challenges_address ON wallet_challenges(wallet_address);
CREATE INDEX IF NOT EXISTS idx_wallet_challenges_expires ON wallet_challenges(expires_at);

-- Cleanup function for expired challenges
CREATE OR REPLACE FUNCTION cleanup_expired_challenges()
RETURNS void AS $$
BEGIN
    DELETE FROM wallet_challenges WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

