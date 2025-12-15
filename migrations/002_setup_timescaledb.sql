-- TimescaleDB Setup
-- Run this AFTER 001_initial_schema.sql
-- Requires superuser privileges or database owner

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Convert apr_snapshots to hypertable
-- Partition by timestamp with daily chunks
SELECT create_hypertable(
    'apr_snapshots', 
    'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Optional: Set up compression for data older than 7 days
-- ALTER TABLE apr_snapshots SET (
--     timescaledb.compress,
--     timescaledb.compress_segmentby = 'blockchain_id, protocol_id, asset_id',
--     timescaledb.compress_orderby = 'timestamp DESC'
-- );

-- Optional: Add compression policy (compress data older than 7 days)
-- SELECT add_compression_policy('apr_snapshots', INTERVAL '7 days');

-- Optional: Add retention policy (delete data older than 2 years)
-- SELECT add_retention_policy('apr_snapshots', INTERVAL '2 years');

