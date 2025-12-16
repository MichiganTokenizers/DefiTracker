# FXRP-USDT0-stXRP Pool Implementation Status

## ✅ Completed

### 1. KineticAdapter Class Structure
**File**: `src/adapters/flare/kinetic.py`

**Implemented**:
- ✅ Class structure with both methods (on-chain)
- ✅ `get_supported_assets()` - Returns ['FXRP', 'USDT0', 'stXRP']
- ✅ `get_supply_apr()` - Method 1: Lens contract query (IMPLEMENTED)
  - Fetches ABI from FlareScan or uses minimal ABI
  - Calls Lens contract or ISO market contract directly
  - Converts supply rate per block to APR percentage
- ✅ `compute_apr_from_onchain()` - Method 2: Historical calculation (structure ready)
- ✅ Helper methods for APR calculation
- ✅ Error handling and logging
- ✅ ABI fetcher utility (`src/adapters/flare/abi_fetcher.py`)

### 2. Integration with FlareChainAdapter
**File**: `src/adapters/flare/chain_adapter.py`

**Implemented**:
- ✅ KineticAdapter initialization
- ✅ Web3 instance passing to KineticAdapter
- ✅ Protocol registration

### 3. Configuration
**File**: `config/chains.yaml`

**Added**:
- ✅ Kinetic protocol configuration
- ✅ Token configuration structure (FXRP, USDT0, stXRP)
- ✅ All contract addresses from Kinetic documentation:
  - Unitroller, Comptroller, Lens addresses
  - Token addresses (FXRP, USDT0, stXRP)
  - ISO market addresses for each token

### 4. ABI Fetching Utility
**File**: `src/adapters/flare/abi_fetcher.py`

**Implemented**:
- ✅ FlareScan API integration to fetch contract ABIs
- ✅ Minimal ABI fallbacks for Lens and cToken contracts
- ✅ Error handling for unverified contracts

## 🔧 TODO: Research & Implementation

### Phase 1: Method 1 - Lens Contract Query ✅ MOSTLY COMPLETE

**Status**: Implemented, needs testing

**What's Done**:
- ✅ ABI fetching from FlareScan
- ✅ Lens contract call implementation
- ✅ Fallback to direct ISO market contract calls
- ✅ Supply rate to APR conversion
- ✅ Error handling

**What's Left**:
- [ ] Test with actual contracts (may need to adjust for actual return format)
- [ ] Verify ABI structure matches actual contracts
- [ ] Handle edge cases (unverified contracts, different ABI versions)
```json
{
  "markets": [
    {
      "token": "FXRP",
      "supply_apr": 3.83,
      "borrow_apr": -2.30,
      "total_supply": 10340000,
      "total_borrowed": 287000
    },
    ...
  ]
}
```

### Phase 2: On-Chain Method (Method 2)

**Tasks**:
1. **Find Contract Addresses**:
   - [ ] FXRP token contract address
   - [ ] USDT0 token contract address
   - [ ] stXRP token contract address
   - [ ] Kinetic protocol contract address

2. **Get Contract ABIs**:
   - [ ] Kinetic protocol ABI
   - [ ] Event signatures for:
     - Reward distribution events
     - Supply/deposit events

3. **Implement On-Chain Queries**:
   - [ ] `_get_rewards_paid()` - Query reward events
   - [ ] `_get_total_volume()` - Query supply events
   - [ ] Filter events by token address
   - [ ] Aggregate totals

**Event Signatures** (to be found):
- Reward distribution: `RewardDistributed(address token, uint256 amount, ...)`
- Supply event: `Supply(address token, uint256 amount, ...)`

### Phase 3: Testing & Integration

**Tasks**:
1. **Test Method 1**:
   - [ ] Test API connection
   - [ ] Verify APR data accuracy
   - [ ] Test error handling

2. **Test Method 2**:
   - [ ] Test Web3 connection
   - [ ] Test event querying
   - [ ] Verify APR calculation
   - [ ] Compare with Method 1 results

3. **Integration Testing**:
   - [ ] Test through ChainRegistry
   - [ ] Test data storage in database
   - [ ] Verify all three tokens (FXRP, USDT0, stXRP)

### Phase 4: Data Collection

**Tasks**:
1. **Update Collector Job**:
   - [ ] Wire KineticAdapter into collection flow
   - [ ] Store APRs for each token
   - [ ] Handle both methods (prefer API, fallback to on-chain)

2. **Database Storage**:
   - [ ] Ensure assets are created (FXRP, USDT0, stXRP)
   - [ ] Store APR snapshots with timestamps
   - [ ] Track which method was used (optional metadata)

## 📋 Research Checklist

### API Research
- [ ] Visit https://docs.kinetic.market
- [ ] Find market/pool data endpoints
- [ ] Test API calls manually
- [ ] Document authentication requirements

### Contract Research
- [ ] Find Kinetic protocol contract on Flare
- [ ] Find FXRP token contract
- [ ] Find USDT0 token contract
- [ ] Find stXRP token contract
- [ ] Get contract ABIs from:
  - FlareScan (https://flare-explorer.flare.network)
  - Kinetic documentation
  - Contract verification

### Event Research
- [ ] Identify reward distribution event signature
- [ ] Identify supply/deposit event signature
- [ ] Test event queries on FlareScan
- [ ] Verify event parameters

## 🎯 Next Immediate Steps

1. **Research Kinetic API**:
   - Check https://docs.kinetic.market for API documentation
   - Test API endpoints for market data
   - Update `_get_apr_from_api()` with real implementation

2. **Find Contract Addresses**:
   - Use FlareScan to find token contracts
   - Find Kinetic protocol contract
   - Update `config/chains.yaml` with real addresses

3. **Test Basic Flow**:
   - Test KineticAdapter initialization
   - Test `get_supported_assets()`
   - Test API method (once endpoint is known)

## 📊 Expected Data Structure

Once implemented, we'll collect:
```json
{
  "flare": {
    "kinetic": {
      "FXRP": 3.83,    // Supply APR %
      "USDT0": 25.44,  // Supply APR %
      "stXRP": 0.0     // Supply APR % (to be determined)
    }
  }
}
```

Stored in database as separate snapshots for each token with timestamps.

