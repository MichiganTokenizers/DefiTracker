# FXRP-USDT0-stXRP Pool Implementation Plan

## Pool Overview
- **Pool Name**: FXRP-USDT0-stXRP (ISO Market on Kinetic)
- **Protocol**: Kinetic
- **Blockchain**: Flare (Chain ID: 14)
- **Tokens**: FXRP, USDT0, stXRP

## Data Collection Methods

### Method 1: Direct API Pull (Simple)
**Source**: Kinetic API
**What we'll get**:
- Stated Supply APR for each token (FXRP, USDT0, stXRP)
- Total Supply for each token
- Total Borrowed for each token

**API Endpoints** (to be verified):
- Market data endpoint (likely `/markets` or `/pools`)
- Token-specific APR endpoints

### Method 2: On-Chain Calculation (Advanced)
**Source**: Flare blockchain via Web3
**What we'll calculate**:
- **Rewards Paid**: Total rewards distributed for each token over a period
- **Volume**: Total supply volume for each token over a period
- **APR Formula**: `APR = (Total Rewards / Average Supply) × (365 / Days)`

**On-Chain Data Needed**:
1. **Rewards Events**: Track reward distribution events from Kinetic contracts
2. **Supply Events**: Track supply/deposit events to calculate volume
3. **Time Period**: Lookback period (e.g., 7 days, 30 days)

## Implementation Structure

### 1. KineticAdapter Class
**File**: `src/adapters/flare/kinetic.py`

**Methods**:
- `get_supported_assets()` → Returns: `['FXRP', 'USDT0', 'stXRP']`
- `get_supply_apr(asset)` → Method 1: Pull from API
- `compute_apr_from_onchain(asset, lookback_days)` → Method 2: Calculate from chain
- `_get_apr_from_api(asset)` → Helper: Fetch from Kinetic API
- `_get_rewards_paid(asset, start_block, end_block)` → Helper: Query rewards events
- `_get_total_volume(asset, start_block, end_block)` → Helper: Query supply volume
- `_calculate_apr_from_metrics(rewards, volume, days)` → Helper: Apply APR formula

### 2. Token Contract Addresses
We'll need the contract addresses for:
- FXRP token contract
- USDT0 token contract  
- stXRP token contract
- Kinetic protocol contract (for events)

### 3. Database Storage
Store data for each token separately:
- `asset_id` for FXRP
- `asset_id` for USDT0
- `asset_id` for stXRP
- Each with its own APR snapshot

## Data Flow

### Method 1 Flow:
```
KineticAdapter.get_supply_apr('FXRP')
  ↓
HTTP GET to Kinetic API
  ↓
Parse response → Extract Supply APR
  ↓
Return Decimal(3.83)  # 3.83%
```

### Method 2 Flow:
```
KineticAdapter.compute_apr_from_onchain('FXRP', lookback_days=7)
  ↓
1. Get current block number
2. Calculate start block (7 days ago)
  ↓
3. Query Kinetic contract events:
   - RewardDistribution events
   - Supply/Deposit events
  ↓
4. Aggregate:
   - Total rewards paid (FXRP)
   - Total volume supplied (FXRP)
  ↓
5. Calculate:
   APR = (rewards / volume) × (365 / 7)
  ↓
Return Decimal(calculated_apr)
```

## APR Calculation Formula

From README:
```
APR ≈ (rewards over period / average supplied over period) × (365 / days in period)
```

**For our implementation**:
```python
def calculate_apr(rewards_paid: Decimal, total_volume: Decimal, days: int) -> Decimal:
    if total_volume == 0:
        return Decimal(0)
    
    # Average supply = total volume / days (simplified)
    # Or use actual average if we track daily snapshots
    average_supply = total_volume / days
    
    # APR calculation
    apr = (rewards_paid / average_supply) * (365 / days) * 100  # Convert to percentage
    return apr
```

## Configuration

**Update `config/chains.yaml`**:
```yaml
chains:
  flare:
    enabled: true
    rpc_url: "https://flare-api.flare.network/ext/C/rpc"
    chain_id: 14
    protocols:
      kinetic:
        enabled: true
        api_url: "https://api.kinetic.market"  # To be verified
        # Token contract addresses
        tokens:
          FXRP:
            address: "0x..."  # To be found
            decimals: 18
          USDT0:
            address: "0x..."  # To be found
            decimals: 6  # USDT typically 6 decimals
          stXRP:
            address: "0x..."  # To be found
            decimals: 18
        # Kinetic protocol contract
        protocol_contract: "0x..."  # To be found
```

## Next Steps

1. **Research Kinetic API**:
   - Find exact API endpoints
   - Test API calls for FXRP-USDT0-stXRP pool
   - Document response format

2. **Find Contract Addresses**:
   - FXRP token contract
   - USDT0 token contract
   - stXRP token contract
   - Kinetic protocol contract

3. **Implement Method 1**:
   - Create API client
   - Parse pool/token data
   - Extract APRs

4. **Implement Method 2**:
   - Set up Web3 connection
   - Query reward events
   - Query supply events
   - Calculate APR

5. **Integration**:
   - Wire into FlareChainAdapter
   - Update collector job
   - Test both methods

6. **Database Storage**:
   - Store APRs for each token
   - Track which method was used
   - Store metadata (rewards, volume) optionally

## Questions to Answer

1. **API Endpoints**: What are the exact Kinetic API endpoints?
2. **Contract Addresses**: What are the token and protocol contract addresses?
3. **Event Signatures**: What are the event signatures for rewards and supply?
4. **Data Format**: What format does the API return?
5. **Method Preference**: Should we prefer API or on-chain, or use both and compare?

