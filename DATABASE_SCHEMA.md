# Database Schema Design

## Overview

The database uses **PostgreSQL with TimescaleDB extension** for efficient time-series data storage. The schema is designed to support multiple blockchains, protocols, and assets with historical APR tracking.

## Schema Layout

### 1. `blockchains` Table
Stores blockchain network information.

```sql
CREATE TABLE blockchains (
    blockchain_id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    chain_id INTEGER UNIQUE NOT NULL,
    rpc_url TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

**Columns:**
- `blockchain_id`: Primary key (auto-increment)
- `name`: Chain name (e.g., 'flare', 'ethereum', 'polygon')
- `chain_id`: Chain ID number (e.g., 14 for Flare, 1 for Ethereum)
- `rpc_url`: RPC endpoint URL (optional, can be in config)
- `enabled`: Whether this chain is actively tracked
- `created_at`, `updated_at`: Timestamps

**Indexes:**
- `idx_blockchains_name`: On `name` (for lookups)
- `idx_blockchains_enabled`: On `enabled` (for filtering active chains)

---

### 2. `protocols` Table
Stores DeFi protocol information.

```sql
CREATE TABLE protocols (
    protocol_id SERIAL PRIMARY KEY,
    blockchain_id INTEGER NOT NULL REFERENCES blockchains(blockchain_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    api_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(blockchain_id, name)
);
```

**Columns:**
- `protocol_id`: Primary key
- `blockchain_id`: Foreign key to `blockchains`
- `name`: Protocol name (e.g., 'kinetic', 'blazeswap', 'aave')
- `enabled`: Whether this protocol is actively tracked
- `api_url`: Optional API endpoint for the protocol
- `created_at`, `updated_at`: Timestamps

**Indexes:**
- `idx_protocols_blockchain`: On `blockchain_id` (for filtering by chain)
- `idx_protocols_enabled`: On `enabled`
- `idx_protocols_blockchain_name`: Composite on `(blockchain_id, name)`

---

### 3. `assets` Table
Stores asset/token information.

```sql
CREATE TABLE assets (
    asset_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    contract_address VARCHAR(66), -- For EVM chains, hex address
    decimals INTEGER DEFAULT 18,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, contract_address)
);
```

**Columns:**
- `asset_id`: Primary key
- `symbol`: Token symbol (e.g., 'FLR', 'USDC', 'ETH')
- `name`: Full name (e.g., 'Flare', 'USD Coin')
- `contract_address`: Contract address (NULL for native tokens)
- `decimals`: Token decimals (default 18)

**Indexes:**
- `idx_assets_symbol`: On `symbol`
- `idx_assets_contract`: On `contract_address`

**Note:** Assets are global (not chain-specific) since the same token symbol might exist on multiple chains. We'll track chain-specific APR data in the snapshots table.

---

### 4. `apr_snapshots` Table (TimescaleDB Hypertable)
Stores historical APR data. This is the main time-series table.

```sql
CREATE TABLE apr_snapshots (
    snapshot_id BIGSERIAL,
    blockchain_id INTEGER NOT NULL REFERENCES blockchains(blockchain_id) ON DELETE CASCADE,
    protocol_id INTEGER NOT NULL REFERENCES protocols(protocol_id) ON DELETE CASCADE,
    asset_id INTEGER NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    apr NUMERIC(10, 4) NOT NULL, -- APR as percentage (e.g., 12.5 for 12.5%)
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_id, timestamp)
);
```

**Columns:**
- `snapshot_id`: Primary key (auto-increment)
- `blockchain_id`: Foreign key to `blockchains`
- `protocol_id`: Foreign key to `protocols`
- `asset_id`: Foreign key to `assets`
- `apr`: APR value as percentage (NUMERIC for precision)
- `timestamp`: When this APR was recorded (used for time-series partitioning)
- `created_at`: When this record was inserted

**Indexes:**
- `idx_apr_snapshots_timestamp`: On `timestamp` (for time-range queries)
- `idx_apr_snapshots_blockchain_protocol`: Composite on `(blockchain_id, protocol_id)`
- `idx_apr_snapshots_asset`: On `asset_id`
- `idx_apr_snapshots_lookup`: Composite on `(blockchain_id, protocol_id, asset_id, timestamp DESC)`

**TimescaleDB:**
- Convert to hypertable for time-series optimization
- Partition by `timestamp` (daily chunks recommended)

---

### 5. `collection_logs` Table (Optional)
Tracks collection job runs for monitoring and debugging.

```sql
CREATE TABLE collection_logs (
    log_id SERIAL PRIMARY KEY,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL, -- 'running', 'completed', 'failed'
    chains_collected INTEGER DEFAULT 0,
    snapshots_created INTEGER DEFAULT 0,
    error_message TEXT,
    metadata JSONB
);
```

**Columns:**
- `log_id`: Primary key
- `started_at`: When collection started
- `completed_at`: When collection finished (NULL if still running)
- `status`: Collection status
- `chains_collected`: Number of chains processed
- `snapshots_created`: Number of snapshots inserted
- `error_message`: Error details if failed
- `metadata`: Additional info (JSON)

**Indexes:**
- `idx_collection_logs_status`: On `status`
- `idx_collection_logs_started`: On `started_at DESC`

---

## Relationships Diagram

```
blockchains (1) ──< (many) protocols
protocols (1) ──< (many) apr_snapshots
blockchains (1) ──< (many) apr_snapshots
assets (1) ──< (many) apr_snapshots
```

## Data Flow

1. **Initialization**: Insert blockchains, protocols, and assets
2. **Collection**: Insert APR snapshots with references to blockchain, protocol, and asset
3. **Querying**: Join tables to get human-readable data

## Example Queries

### Get latest APRs for a chain
```sql
SELECT 
    p.name AS protocol,
    a.symbol AS asset,
    s.apr,
    s.timestamp
FROM apr_snapshots s
JOIN protocols p ON s.protocol_id = p.protocol_id
JOIN assets a ON s.asset_id = a.asset_id
JOIN blockchains b ON s.blockchain_id = b.blockchain_id
WHERE b.name = 'flare'
  AND s.timestamp = (
      SELECT MAX(timestamp) 
      FROM apr_snapshots 
      WHERE blockchain_id = s.blockchain_id 
        AND protocol_id = s.protocol_id 
        AND asset_id = s.asset_id
  )
ORDER BY p.name, a.symbol;
```

### Get historical APR for an asset
```sql
SELECT 
    s.timestamp,
    s.apr,
    p.name AS protocol,
    b.name AS blockchain
FROM apr_snapshots s
JOIN protocols p ON s.protocol_id = p.protocol_id
JOIN assets a ON s.asset_id = a.asset_id
JOIN blockchains b ON s.blockchain_id = b.blockchain_id
WHERE a.symbol = 'FLR'
  AND s.timestamp >= NOW() - INTERVAL '30 days'
ORDER BY s.timestamp DESC;
```

### Get average APR over time period
```sql
SELECT 
    time_bucket('1 day', timestamp) AS day,
    AVG(apr) AS avg_apr,
    MIN(apr) AS min_apr,
    MAX(apr) AS max_apr
FROM apr_snapshots
WHERE blockchain_id = 1
  AND protocol_id = 1
  AND asset_id = 1
  AND timestamp >= NOW() - INTERVAL '7 days'
GROUP BY day
ORDER BY day;
```

## TimescaleDB Benefits

1. **Automatic Partitioning**: Data partitioned by time for efficient queries
2. **Compression**: Automatic compression of old data
3. **Continuous Aggregates**: Pre-computed aggregations for fast queries
4. **Retention Policies**: Automatic deletion of old data
5. **Time-based Functions**: `time_bucket()` for efficient grouping

## Migration Strategy

1. Create base tables (blockchains, protocols, assets)
2. Create apr_snapshots table
3. Convert apr_snapshots to TimescaleDB hypertable
4. Create indexes
5. Insert initial data (blockchains, protocols from config)

