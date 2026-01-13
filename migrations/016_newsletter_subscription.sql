-- Newsletter Subscription Field
-- Migration: 016_newsletter_subscription.sql
-- Adds newsletter subscription tracking for users

-- Add newsletter_subscribed column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS newsletter_subscribed BOOLEAN DEFAULT FALSE;

-- Index for querying newsletter subscribers
CREATE INDEX IF NOT EXISTS idx_users_newsletter ON users(newsletter_subscribed) WHERE newsletter_subscribed = TRUE;

