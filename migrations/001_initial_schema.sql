-- Multi-Chain DeFi APR Tracker - Initial Schema
-- PostgreSQL with TimescaleDB extension

-- Enable TimescaleDB extension (must be run as superuser)
-- CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================
-- 1. Blockchains Table
-- ============================================
CREATE TABLE IF NOT EXISTS blockchains (
    blockchain_id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    chain_id INTEGER UNIQUE NOT NULL,
    rpc_url TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_blockchains_name ON blockchains(name);
CREATE INDEX IF NOT EXISTS idx_blockchains_enabled ON blockchains(enabled);

-- ============================================
-- 2. Protocols Table
-- ============================================
CREATE TABLE IF NOT EXISTS protocols (
    protocol_id SERIAL PRIMARY KEY,
    blockchain_id INTEGER NOT NULL REFERENCES blockchains(blockchain_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    api_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(blockchain_id, name)
);

CREATE INDEX IF NOT EXISTS idx_protocols_blockchain ON protocols(blockchain_id);
CREATE INDEX IF NOT EXISTS idx_protocols_enabled ON protocols(enabled);
CREATE INDEX IF NOT EXISTS idx_protocols_blockchain_name ON protocols(blockchain_id, name);

-- ============================================
-- 3. Assets Table
-- ============================================
CREATE TABLE IF NOT EXISTS assets (
    asset_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    contract_address VARCHAR(66), -- For EVM chains, hex address
    decimals INTEGER DEFAULT 18,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, contract_address)
);

CREATE INDEX IF NOT EXISTS idx_assets_symbol ON assets(symbol);
CREATE INDEX IF NOT EXISTS idx_assets_contract ON assets(contract_address);

-- ============================================
-- 4. APR Snapshots Table (TimescaleDB Hypertable)
-- ============================================
CREATE TABLE IF NOT EXISTS apr_snapshots (
    snapshot_id BIGSERIAL,
    blockchain_id INTEGER NOT NULL REFERENCES blockchains(blockchain_id) ON DELETE CASCADE,
    protocol_id INTEGER NOT NULL REFERENCES protocols(protocol_id) ON DELETE CASCADE,
    asset_id INTEGER NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    apr NUMERIC(10, 4) NOT NULL, -- APR as percentage (e.g., 12.5 for 12.5%)
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_id, timestamp)
);

-- Create indexes before converting to hypertable
CREATE INDEX IF NOT EXISTS idx_apr_snapshots_timestamp ON apr_snapshots(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_apr_snapshots_blockchain_protocol ON apr_snapshots(blockchain_id, protocol_id);
CREATE INDEX IF NOT EXISTS idx_apr_snapshots_asset ON apr_snapshots(asset_id);
CREATE INDEX IF NOT EXISTS idx_apr_snapshots_lookup ON apr_snapshots(blockchain_id, protocol_id, asset_id, timestamp DESC);

-- Convert to TimescaleDB hypertable
-- This must be run after the table is created
-- SELECT create_hypertable('apr_snapshots', 'timestamp', chunk_time_interval => INTERVAL '1 day');

-- ============================================
-- 5. Collection Logs Table (Optional - for monitoring)
-- ============================================
CREATE TABLE IF NOT EXISTS collection_logs (
    log_id SERIAL PRIMARY KEY,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL DEFAULT 'running', -- 'running', 'completed', 'failed'
    chains_collected INTEGER DEFAULT 0,
    snapshots_created INTEGER DEFAULT 0,
    error_message TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_collection_logs_status ON collection_logs(status);
CREATE INDEX IF NOT EXISTS idx_collection_logs_started ON collection_logs(started_at DESC);

-- ============================================
-- Helper Functions
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_blockchains_updated_at BEFORE UPDATE ON blockchains
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_protocols_updated_at BEFORE UPDATE ON protocols
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

