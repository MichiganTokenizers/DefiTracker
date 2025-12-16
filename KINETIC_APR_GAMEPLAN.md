# Kinetic APR Collection Gameplan

## Overview
This document outlines the plan for pulling APR data from Kinetic protocol on the Flare blockchain.

## What is Kinetic?
- **Platform**: Overcollateralized lending protocol on Flare blockchain
- **Function**: Peer-to-peer borrowing with dynamic interest rates
- **Website**: https://kinetic-market.org
- **API Docs**: https://docs.kinetic.xyz

## Data We'll Be Pulling

### 1. **Supply APRs** (Primary Focus)
- **What**: Annual Percentage Rate for supplying/lending assets
- **Assets**: USDC, USDT, and other supported tokens
- **Format**: Percentage value (e.g., 12.5 for 12.5% APR)
- **Update Frequency**: Real-time (we'll collect daily snapshots)

### 2. **Asset Information** (Metadata)
- Asset symbols (USDC, USDT, etc.)
- Asset names
- Contract addresses (for Flare blockchain)
- Token decimals

### 3. **Market Data** (Optional, for context)
- Total Value Locked (TVL)
- Total supply/borrow volumes
- Utilization rates

## Data Source: Kinetic API

### API Endpoints
- **Base URL**: `https://api.kinetic.xyz`
- **Authentication**: Required (API key → JWT token)
- **Auth Endpoint**: `https://auth.kinetic.xyz/v1/token`

### Expected API Structure (to be verified)
Based on typical DeFi lending APIs, we'll likely need:
- `/markets` or `/assets` - List all supported markets/assets
- `/markets/{asset}/supply-rate` - Get current supply APR
- `/markets/{asset}/borrow-rate` - Get current borrow APR (optional)

**Note**: We'll need to inspect the actual API documentation or make test calls to confirm the exact endpoints.

## Implementation Plan

### Phase 1: Create Kinetic Protocol Adapter
**File**: `src/adapters/flare/kinetic.py`

**What it will do**:
1. Implement `ProtocolAdapter` interface
2. Connect to Kinetic API
3. Fetch supply APRs for all supported assets
4. Handle authentication (API key → JWT)
5. Parse and return APR data

**Key Methods**:
- `get_supported_assets()` → List of asset symbols (USDC, USDT, etc.)
- `get_supply_apr(asset)` → APR for a specific asset
- `compute_apr_from_onchain()` → Fallback if API fails (optional)

### Phase 2: Integrate with Flare Chain Adapter
**File**: `src/adapters/flare/chain_adapter.py`

**What it will do**:
1. Import and initialize `KineticAdapter`
2. Register it in the `protocols` dictionary
3. Enable APR collection via `collect_aprs()` method

### Phase 3: Store Data in Database
**File**: `src/scheduler/collector_job.py`

**What it will do**:
1. Use `ChainRegistry` to collect APRs
2. For each asset with APR data:
   - Get/create asset in database
   - Get/create protocol (kinetic) in database
   - Insert APR snapshot with timestamp
3. Log collection results

### Phase 4: Configuration
**File**: `config/chains.yaml`

**What we'll add**:
```yaml
kinetic:
  enabled: true
  api_key: YOUR_API_KEY_HERE  # Optional, if required
  api_url: https://api.kinetic.xyz
```

## Data Flow

```
1. Scheduler triggers collection (daily at midnight UTC)
   ↓
2. ChainRegistry.collect_all_aprs()
   ↓
3. FlareChainAdapter.collect_aprs()
   ↓
4. KineticAdapter.get_supply_apr(asset) for each asset
   ↓
5. Returns: { "USDC": 12.5, "USDT": 10.2, ... }
   ↓
6. collector_job stores in database:
   - Get/create asset (USDC, USDT, etc.)
   - Get/create protocol (kinetic)
   - Insert APR snapshot with timestamp
   ↓
7. Data stored in apr_snapshots table
```

## Database Schema (Already Created)

The data will be stored in:
- **`assets`** table: Asset information (USDC, USDT, etc.)
- **`protocols`** table: Protocol info (kinetic)
- **`apr_snapshots`** table: Time-series APR data
  - Columns: `blockchain_id`, `protocol_id`, `asset_id`, `apr`, `timestamp`

## What We Need to Implement

### 1. Kinetic API Client
- [ ] Research actual API endpoints (may need to inspect network requests)
- [ ] Implement authentication flow (API key → JWT)
- [ ] Create HTTP client with error handling
- [ ] Parse API responses

### 2. KineticAdapter Class
- [ ] Implement `get_supported_assets()` - Fetch list from API
- [ ] Implement `get_supply_apr(asset)` - Fetch APR for asset
- [ ] Implement `compute_apr_from_onchain()` - Optional fallback
- [ ] Handle API errors gracefully

### 3. Integration
- [ ] Wire up KineticAdapter in FlareChainAdapter
- [ ] Update collector_job to store data in database
- [ ] Add configuration for API key (if needed)

### 4. Testing
- [ ] Test API connection
- [ ] Test APR data retrieval
- [ ] Test database storage
- [ ] Verify data accuracy

## Next Steps

1. **Research Kinetic API**: 
   - Visit https://docs.kinetic.xyz to find exact endpoints
   - Check if API key is required
   - Test API calls manually (curl/Postman)

2. **Create KineticAdapter**: 
   - Start with basic API client
   - Implement required methods
   - Add error handling

3. **Test Integration**:
   - Run collector manually
   - Verify data in database
   - Check data accuracy

4. **Schedule Collection**:
   - Enable scheduler for daily collection
   - Monitor logs for errors

## Questions to Answer

1. **API Access**: Does Kinetic require an API key, or is it public?
2. **Endpoints**: What are the exact API endpoints for market data?
3. **Rate Limits**: Are there API rate limits we need to respect?
4. **Asset List**: What assets does Kinetic currently support?
5. **Data Format**: What format does the API return (JSON structure)?

## Expected Data Structure

Once implemented, we'll store data like:
```json
{
  "blockchain": "flare",
  "protocol": "kinetic",
  "asset": "USDC",
  "apr": 12.5,
  "timestamp": "2024-01-15T00:00:00Z"
}
```

This will allow us to:
- Track APR changes over time
- Compare APRs across different assets
- Provide historical data via API
- Create charts and visualizations

