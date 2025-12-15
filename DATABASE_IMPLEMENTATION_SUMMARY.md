# Database Layer Implementation Summary

## What Was Created

### 1. Schema Design Document
**File:** `DATABASE_SCHEMA.md`
- Complete schema layout with all tables
- Relationships and indexes
- Example queries
- TimescaleDB benefits explanation

### 2. SQL Migration Files
**Files:** 
- `migrations/001_initial_schema.sql` - Creates all tables and indexes
- `migrations/002_setup_timescaledb.sql` - Sets up TimescaleDB hypertable

**Tables Created:**
1. `blockchains` - Blockchain network information
2. `protocols` - DeFi protocol information (linked to blockchains)
3. `assets` - Token/asset information
4. `apr_snapshots` - Time-series APR data (TimescaleDB hypertable)
5. `collection_logs` - Collection job tracking

### 3. Database Query Module
**File:** `src/database/queries.py`

**Key Classes:**
- `DatabaseQueries` - All database operations

**Methods Provided:**

#### Blockchain Operations
- `get_or_create_blockchain()` - Get or create blockchain entry
- `get_blockchain_id()` - Get blockchain ID by name
- `get_all_blockchains()` - List all active blockchains

#### Protocol Operations
- `get_or_create_protocol()` - Get or create protocol entry
- `get_protocol_id()` - Get protocol ID

#### Asset Operations
- `get_or_create_asset()` - Get or create asset entry
- `get_asset_id()` - Get asset ID

#### APR Snapshot Operations
- `insert_apr_snapshot()` - Insert single APR snapshot
- `insert_bulk_apr_snapshots()` - Efficient bulk insert
- `get_latest_aprs()` - Get latest APR values (with filters)
- `get_historical_aprs()` - Get historical data for an asset
- `get_apr_statistics()` - Get avg/min/max APR over time period

#### Collection Log Operations
- `start_collection_log()` - Start tracking a collection job
- `complete_collection_log()` - Complete collection log entry

### 4. Database Setup Script
**File:** `src/database/setup.py`

**Functions:**
- `setup_database()` - Run migrations and create schema
- `initialize_from_config()` - Initialize blockchains/protocols from `chains.yaml`
- `verify_setup()` - Verify database setup is correct

**Usage:**
```bash
python src/database/setup.py
```

### 5. Setup Guide
**File:** `DATABASE_SETUP_GUIDE.md`
- Step-by-step installation instructions
- Troubleshooting guide
- Production considerations

## Database Schema Overview

```
┌──────────────┐
│ blockchains  │
│──────────────│
│ blockchain_id│──┐
│ name         │  │
│ chain_id     │  │
│ enabled      │  │
└──────────────┘  │
                  │
                  │ 1:N
                  │
┌──────────────┐  │
│  protocols   │  │
│──────────────│  │
│ protocol_id  │◄─┘
│ blockchain_id│──┐
│ name         │  │
│ enabled      │  │
└──────────────┘  │
                  │
                  │ 1:N
                  │
┌──────────────┐  │      ┌──────────────┐
│apr_snapshots │  │      │    assets    │
│──────────────│  │      │──────────────│
│ snapshot_id  │  │      │  asset_id    │──┐
│ blockchain_id│◄─┘      │  symbol      │  │
│ protocol_id  │◄────────┼  name        │  │
│ asset_id     │◄────────┘  contract   │  │
│ apr          │                        │  │
│ timestamp    │                        │  │
└──────────────┘                        │  │
                                        │  │
                                        │  │ 1:N
                                        │  │
                                        │  │
                                        └──┘
```

## How to Use

### 1. Set Up Database
```bash
# Install PostgreSQL and TimescaleDB (see DATABASE_SETUP_GUIDE.md)
# Configure config/database.yaml
python src/database/setup.py
```

### 2. Use in Your Code

#### Insert APR Data
```python
from src.database.queries import DatabaseQueries
from decimal import Decimal
from datetime import datetime

queries = DatabaseQueries()

# Get or create IDs
blockchain_id = queries.get_or_create_blockchain('flare', 14)
protocol_id = queries.get_or_create_protocol(blockchain_id, 'kinetic')
asset_id = queries.get_or_create_asset('FLR', 'Flare')

# Insert APR snapshot
snapshot_id = queries.insert_apr_snapshot(
    blockchain_id=blockchain_id,
    protocol_id=protocol_id,
    asset_id=asset_id,
    apr=Decimal('12.5'),
    timestamp=datetime.utcnow()
)
```

#### Query Latest APRs
```python
# Get all latest APRs
latest = queries.get_latest_aprs()

# Get latest APRs for specific chain
flare_aprs = queries.get_latest_aprs(blockchain_name='flare')

# Get latest APR for specific asset
flr_apr = queries.get_latest_aprs(
    blockchain_name='flare',
    protocol_name='kinetic',
    asset_symbol='FLR'
)
```

#### Query Historical Data
```python
# Get 30 days of history
history = queries.get_historical_aprs(
    blockchain_name='flare',
    protocol_name='kinetic',
    asset_symbol='FLR',
    days=30
)

# Get statistics
stats = queries.get_apr_statistics(
    blockchain_name='flare',
    protocol_name='kinetic',
    asset_symbol='FLR',
    days=7
)
# Returns: {'avg_apr': 12.5, 'min_apr': 10.2, 'max_apr': 15.3, 'data_points': 7}
```

### 3. Integration with Scheduler

Update `src/scheduler/collector_job.py` to use the database:

```python
from src.database.queries import DatabaseQueries
from decimal import Decimal

def collect_apr_data():
    registry = ChainRegistry()
    queries = DatabaseQueries()
    
    # Start collection log
    log_id = queries.start_collection_log()
    
    try:
        all_aprs = registry.collect_all_aprs()
        snapshots = []
        
        for chain_name, chain_data in all_aprs.items():
            blockchain_id = queries.get_blockchain_id(chain_name)
            
            for protocol_name, protocol_data in chain_data.items():
                protocol_id = queries.get_protocol_id(blockchain_id, protocol_name)
                
                for asset_symbol, apr_value in protocol_data.items():
                    if apr_value is None:
                        continue
                    
                    asset_id = queries.get_asset_id(asset_symbol)
                    if not asset_id:
                        asset_id = queries.get_or_create_asset(asset_symbol)
                    
                    snapshots.append((
                        blockchain_id,
                        protocol_id,
                        asset_id,
                        Decimal(str(apr_value)),
                        datetime.utcnow()
                    ))
        
        # Bulk insert
        count = queries.insert_bulk_apr_snapshots(snapshots)
        queries.complete_collection_log(log_id, 'completed', len(all_aprs), count)
        
    except Exception as e:
        queries.complete_collection_log(log_id, 'failed', 0, 0, str(e))
        raise
```

## Key Features

1. **Automatic ID Management** - `get_or_create_*` methods handle ID lookups
2. **Bulk Operations** - Efficient bulk inserts for multiple snapshots
3. **Flexible Queries** - Filter by chain, protocol, or asset
4. **Time-Series Optimized** - TimescaleDB hypertable for efficient queries
5. **Error Handling** - Proper transaction management and rollback
6. **Connection Pooling** - Already implemented in `DatabaseConnection`

## Next Steps

1. ✅ Database schema designed
2. ✅ Migration files created
3. ✅ Query functions implemented
4. ✅ Setup script created
5. ⏭️ **Next:** Integrate with scheduler to store collected APRs
6. ⏭️ **Next:** Add API endpoints for historical data queries
7. ⏭️ **Next:** Test with real data collection

## Testing

Test the database layer:

```python
# Test connection
from src.database.connection import DatabaseConnection
db = DatabaseConnection()
conn = db.get_connection()
print("✓ Connection works")
db.return_connection(conn)

# Test queries
from src.database.queries import DatabaseQueries
queries = DatabaseQueries()

# Test blockchain creation
blockchain_id = queries.get_or_create_blockchain('test_chain', 9999)
print(f"✓ Created blockchain: {blockchain_id}")

# Test retrieval
blockchains = queries.get_all_blockchains()
print(f"✓ Found {len(blockchains)} blockchains")
```

