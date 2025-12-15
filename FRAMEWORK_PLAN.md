# Multi-Chain DeFi APR Tracker - Framework Plan

## Overview
A Python-based system for tracking APR (Annual Percentage Rate) data across multiple blockchain networks. The system collects daily APR data from various DeFi protocols, stores it in TimescaleDB, and provides a REST API and web interface for visualization.

## Current State Assessment

### ✅ Completed Components
- Basic project structure with modular architecture
- Base adapter classes (`ProtocolAdapter`, `ChainAdapter`)
- Flare chain adapter skeleton
- Chain registry system
- Database models (`APRSnapshot`)
- Flask API with basic endpoints
- Scheduler setup with APScheduler
- Configuration files (YAML-based)

### ⚠️ Incomplete Components
- Protocol adapters (Kinetic, BlazeSwap) - not implemented
- Database connection and queries - skeleton only
- Chain registry methods (`get_all_active_chains`, `collect_all_aprs`) - missing
- API endpoints for historical data - not implemented
- Web frontend - not started
- Error handling and logging - basic only
- Data persistence - TODO comments indicate not implemented

## Architecture Framework

### 1. Adapter Layer (`src/adapters/`)
**Purpose**: Abstract interface for different chains and protocols

#### Base Classes
- ✅ `ProtocolAdapter` (abstract base)
  - `get_supply_apr(asset)` - Fetch from API
  - `compute_apr_from_onchain(asset, lookback_days)` - Calculate from on-chain data
  - `get_supported_assets()` - List supported assets

- ✅ `ChainAdapter` (abstract base)
  - `initialize_protocols()` - Load protocol adapters
  - `get_web3_instance()` - Get Web3 connection
  - `collect_aprs()` - Collect from all protocols

#### Implementation Status
- ✅ Flare chain adapter skeleton
- ❌ Protocol adapters (Kinetic, BlazeSwap)
- ❌ Other chain adapters (Ethereum, etc.)

### 2. Collector Layer (`src/collectors/`)
**Purpose**: Orchestrate data collection across chains

#### Components Needed
- ✅ `ChainRegistry` - Manage multiple chains
  - ✅ `get_all_active_chains()` - Basic implementation exists, needs enhancements
  - ✅ `collect_all_aprs()` - Basic implementation exists, needs enhancements
  - ✅ Chain initialization logic - Implemented with lazy loading
  - ⚠️ Missing: Error handling improvements
  - ⚠️ Missing: Parallel collection support
  - ⚠️ Missing: Retry logic
  - ⚠️ Missing: Rate limiting

- ❌ `DataCollector` - Main collection orchestrator
- ❌ Error recovery and retry logic
- ❌ Rate limiting for API calls

### 3. Database Layer (`src/database/`)
**Purpose**: Store and retrieve historical APR data

#### Components Needed
- ⚠️ `connection.py` - Database connection management
  - Connection pooling
  - TimescaleDB setup
  - Migration support

- ✅ `models.py` - Data models
  - `APRSnapshot` model defined
  - ❌ Missing: Database schema creation
  - ❌ Missing: CRUD operations
  - ❌ Missing: Time-series queries

- ❌ `queries.py` - Database query functions
  - Insert APR snapshots
  - Query historical data
  - Aggregate queries (avg, min, max)
  - Time-range queries

### 4. API Layer (`src/api/`)
**Purpose**: REST API for frontend and external access

#### Current Endpoints
- ✅ `/health` - Health check
- ✅ `/chains` - List chains (needs implementation)
- ✅ `/aprs` - Get current APRs (basic)
- ✅ `/aprs/<chain_name>` - Chain-specific APRs

#### Missing Endpoints
- ❌ `/aprs/historical` - Historical data queries
- ❌ `/aprs/<chain_name>/<protocol>` - Protocol-specific
- ❌ `/aprs/<chain_name>/<protocol>/<asset>` - Asset-specific
- ❌ `/stats` - Aggregate statistics
- ❌ `/chains/<chain_name>/protocols` - List protocols per chain

#### Improvements Needed
- Error handling middleware
- Request validation
- Response pagination
- Caching layer
- API documentation (Swagger/OpenAPI)

### 5. Scheduler Layer (`src/scheduler/`)
**Purpose**: Automated data collection

#### Current State
- ✅ Basic scheduler setup
- ⚠️ Collection function has TODO for database storage
- ❌ Missing: Error notification
- ❌ Missing: Collection status tracking
- ❌ Missing: Manual trigger endpoint

### 6. Frontend (Not Started)
**Purpose**: Web interface for visualization

#### Components Needed
- ❌ React/Vue/Angular application
- ❌ Dashboard with charts
- ❌ Chain/protocol/asset selection
- ❌ Historical data visualization
- ❌ Comparison tools
- ❌ Real-time updates (WebSocket or polling)

## Implementation Roadmap

### Phase 1: Core Framework Completion
**Priority: HIGH**

1. **Enhance Chain Registry**
   - [x] Basic `get_all_active_chains()` - exists, needs metadata enhancement
   - [x] Basic `collect_all_aprs()` - exists, needs improvements
   - [x] Chain initialization logic - implemented
   - [ ] Improve error handling (logging, status tracking)
   - [ ] Add parallel collection support
   - [ ] Add retry logic with exponential backoff
   - [ ] Add rate limiting for RPC calls
   - [ ] Add collection metadata (timestamps, status)

2. **Database Layer**
   - [ ] Complete `connection.py` with TimescaleDB setup
   - [ ] Create database schema/migrations
   - [ ] Implement CRUD operations in `queries.py`
   - [ ] Add time-series query functions

3. **Protocol Adapters**
   - [ ] Implement Kinetic adapter for Flare
   - [ ] Implement BlazeSwap adapter for Flare
   - [ ] Test APR calculation logic

4. **Scheduler Integration**
   - [ ] Connect collector to database storage
   - [ ] Add error handling and logging
   - [ ] Add collection status tracking

### Phase 2: API Enhancement
**Priority: MEDIUM**

1. **Complete Existing Endpoints**
   - [ ] Fix `/chains` endpoint implementation
   - [ ] Add query parameters (date range, protocol filter)
   - [ ] Add response pagination

2. **Add Historical Endpoints**
   - [ ] `/aprs/historical` with date range
   - [ ] Protocol and asset-specific endpoints
   - [ ] Statistics endpoints

3. **API Improvements**
   - [ ] Add request validation
   - [ ] Add error handling middleware
   - [ ] Add API documentation
   - [ ] Add rate limiting

### Phase 3: Frontend Development
**Priority: MEDIUM**

1. **Setup Frontend Project**
   - [ ] Choose framework (React recommended)
   - [ ] Setup build tooling
   - [ ] Create project structure

2. **Core Components**
   - [ ] Dashboard layout
   - [ ] Chain/protocol selector
   - [ ] APR display cards
   - [ ] Historical charts (using Chart.js or similar)

3. **Advanced Features**
   - [ ] Comparison views
   - [ ] Export functionality
   - [ ] Real-time updates
   - [ ] Mobile responsive design

### Phase 4: Multi-Chain Expansion
**Priority: LOW**

1. **Add New Chains**
   - [ ] Ethereum adapter
   - [ ] Polygon adapter
   - [ ] Arbitrum adapter
   - [ ] Other EVM chains

2. **Protocol Support**
   - [ ] Aave (multi-chain)
   - [ ] Compound (multi-chain)
   - [ ] Uniswap (multi-chain)
   - [ ] Other major protocols

## Technical Decisions Needed

### Database
- ✅ Decision: TimescaleDB (PostgreSQL extension)
- ⚠️ Need: Schema design for multi-chain support
- ⚠️ Need: Migration strategy

### API Framework
- ✅ Decision: Flask
- ⚠️ Consider: FastAPI for better async support and auto-docs?

### Frontend Framework
- ❌ Decision needed: React vs Vue vs Angular
- ❌ Decision needed: Charting library (Chart.js, D3.js, Recharts)

### Deployment
- ❌ Decision needed: Containerization (Docker)
- ❌ Decision needed: Hosting platform
- ❌ Decision needed: CI/CD pipeline

## Configuration Structure

### `config/chains.yaml`
```yaml
chains:
  flare:
    enabled: true
    rpc_url: "..."
    chain_id: 14
    protocols:
      kinetic:
        enabled: true
        api_url: "..."
        contracts: {...}
      blazeswap:
        enabled: true
        ...
```

### `config/database.yaml`
```yaml
database:
  host: localhost
  port: 5432
  name: defi_apr_tracker
  user: ...
  password: ...
  timescale_enabled: true
```

## Testing Strategy

### Unit Tests
- [ ] Adapter tests (mock Web3, mock APIs)
- [ ] Database query tests
- [ ] API endpoint tests

### Integration Tests
- [ ] End-to-end collection flow
- [ ] Database persistence tests
- [ ] API integration tests

### E2E Tests
- [ ] Full collection → storage → retrieval flow
- [ ] Frontend → API → Database flow

## Next Steps (Immediate)

1. **Complete Chain Registry** - Make existing code functional
2. **Implement Database Layer** - Enable data persistence
3. **Create First Protocol Adapter** - Kinetic for Flare
4. **Connect Scheduler to Database** - Make collection actually work
5. **Test End-to-End** - Verify data flow works

## Notes

- Start with Flare chain only, expand later
- Focus on getting one protocol (Kinetic) working end-to-end
- Use existing structure, fill in missing pieces
- Prioritize backend completion before frontend

