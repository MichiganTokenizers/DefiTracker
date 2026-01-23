-- Add wallet_type to users table
-- Migration: 018_add_wallet_type.sql
-- Tracks which Cardano wallet the user logged in with (nami, eternl, lace, etc.)

ALTER TABLE users ADD COLUMN IF NOT EXISTS wallet_type VARCHAR(50);

-- Add comment for documentation
COMMENT ON COLUMN users.wallet_type IS 'CIP-30 wallet identifier used for login (e.g., nami, eternl, lace, yoroi, begin, gerowallet, typhoncip30, nufi)';
