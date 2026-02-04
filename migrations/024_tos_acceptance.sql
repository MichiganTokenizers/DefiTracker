-- Terms of Service Acceptance Tracking
-- Migration: 024_tos_acceptance.sql
-- Tracks when users accept Terms of Service and Privacy Policy

-- Add ToS acceptance columns to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS tos_version VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS tos_accepted_at TIMESTAMP WITH TIME ZONE;

-- Index for querying users who need to re-accept ToS
CREATE INDEX IF NOT EXISTS idx_users_tos_version ON users(tos_version) WHERE tos_version IS NOT NULL;

-- ToS version history table for auditing
CREATE TABLE IF NOT EXISTS tos_versions (
    version_id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL UNIQUE,
    effective_date DATE NOT NULL,
    tos_url VARCHAR(255) NOT NULL,
    privacy_url VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert initial version
INSERT INTO tos_versions (version, effective_date, tos_url, privacy_url)
VALUES ('1.0', CURRENT_DATE, '/terms', '/privacy')
ON CONFLICT (version) DO NOTHING;
