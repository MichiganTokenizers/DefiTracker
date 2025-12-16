# Event Query Implementation - Historical APR Calculation

## Overview

We've implemented **Method 2** for calculating APRs from historical on-chain data by querying events from proxy contracts. This approach works even without full contract ABIs by using event signatures.

## Implementation Details

### How It Works

1. **Query Events from Proxy Contracts**: Uses event signatures (keccak256 hashes) to query logs
2. **No ABI Required**: Works with proxy contracts that don't have verified ABIs on FlareScan
3. **Multiple Data Sources**: Queries multiple event types to get comprehensive data

### Event Queries Implemented

#### 1. Rewards Paid (`_get_rewards_paid`)

**Sources:**
- **AccrueInterest Events**: From ISO market contracts
  - Event: `AccrueInterest(uint256,uint256,uint256,uint256)`
  - Tracks interest accrual which represents rewards
  - Extracts `interestAccumulated` (second parameter)

- **Transfer Events**: From token contracts to reward contracts
  - Event: `Transfer(address,address,uint256)`
  - Queries transfers TO known reward contract addresses:
    - `0xb52aB55F9325B4522c3bdAc692D4F21b0CbA05Ee` (Lending Rebates Rewards)
    - `0x5896c198e445E269021B04D7c84FA46dc2cEdcd8` (Borrow Rebates Rewards)
    - `0x1218b178e170E8cfb3Ba5ADa853aaF4579845347` (Kii Staking Rewards)

**Process:**
1. Calculate event signature hash (keccak256)
2. Query logs using `web3.eth.get_logs()` with event topic
3. Decode event data to extract amounts
4. Sum all rewards over the time period

#### 2. Total Volume (`_get_total_volume`)

**Sources:**
- **Mint Events**: From ISO market contracts
  - Event: `Mint(address,uint256,uint256)`
  - Tracks supply/deposit amounts
  - Extracts `mintAmount` (first parameter)

- **Current Total Supply**: Fallback method
  - Queries `totalSupply()` function directly
  - Uses as approximation if historical events unavailable

**Process:**
1. Query Mint events from ISO market contract
2. Sum all mint amounts over the time period
3. Fallback to current total supply if needed
4. Convert from cToken units to underlying token units

### APR Calculation

Once we have rewards and volume:

```python
APR = (total_rewards / average_supply) × (365 / days) × 100
```

Where:
- `total_rewards`: Sum of all rewards paid over the period
- `average_supply`: Total volume / days (or actual daily average if tracked)
- `days`: Lookback period (e.g., 7, 30 days)

## Usage

### Method 2: Historical Calculation

```python
from src.adapters.flare.kinetic import KineticAdapter

adapter = KineticAdapter('kinetic', config)
adapter.set_web3_instance(web3_instance)

# Calculate APR from 7 days of historical data
apr = adapter.compute_apr_from_onchain('FXRP', lookback_days=7)
```

### What Gets Queried

For a 7-day lookback:
1. **Block Range**: Current block - (7 days × blocks_per_day)
2. **Rewards**: All AccrueInterest and Transfer events in range
3. **Volume**: All Mint events in range
4. **Calculation**: APR = (rewards / volume) × (365 / 7) × 100

## Advantages

✅ **Works without ABIs**: Uses event signatures only
✅ **Works with proxy contracts**: Queries events from any contract
✅ **Historical data**: Can calculate APRs for any time period
✅ **Multiple sources**: Queries multiple event types for accuracy
✅ **Fallback methods**: Has backup approaches if primary fails

## Limitations

⚠️ **Event availability**: Depends on events being emitted
⚠️ **Block range limits**: Some RPCs limit query range
⚠️ **Gas costs**: Large block ranges may be slow
⚠️ **Approximation**: Uses average supply, not exact daily snapshots

## Next Steps

1. **Test with real data**: Run `compute_apr_from_onchain()` and verify results
2. **Optimize queries**: Add caching, batch queries, etc.
3. **Add daily snapshots**: Track daily supply for more accurate averages
4. **Compare with Method 1**: Once Method 1 works, compare both methods

## Event Signatures Used

- `AccrueInterest(uint256,uint256,uint256,uint256)` → Interest accrual
- `Transfer(address,address,uint256)` → Token transfers
- `Mint(address,uint256,uint256)` → Supply deposits

All signatures are calculated using keccak256 and used as event topic filters.

