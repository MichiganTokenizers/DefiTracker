# BlazeSwap Price Feed Implementation

## Overview
Implemented a price feed from BlazeSwap DEX to get real-time rFLR token prices for accurate distribution APR calculations in Kinetic protocol.

## Implementation Status

### ✅ Completed

1. **BlazeSwapPriceFeed Class** (`src/adapters/flare/blazeswap_price.py`)
   - Uniswap V2 style router interface
   - `get_price()` - Basic price query
   - `get_price_with_decimals()` - Price query with explicit decimal handling
   - `get_pair_reserves()` - Direct pair contract reserve queries
   - Graceful error handling when router unavailable

2. **Integration with Kinetic Adapter**
   - `_get_reward_token_price()` method updated to use BlazeSwap
   - Falls back to estimated prices when router unavailable
   - Proper decimal handling for different tokens

3. **Configuration**
   - Added BlazeSwap router address placeholder in `config/chains.yaml`
   - Router address passed through parent config

### ⚠️ Pending

**BlazeSwap Router Address**
- Current placeholder: `0x5C7F8A570d578ED84E63fdFA7b1eE72dEae1AE23` (needs verification)
- Need to find actual router address from:
  1. BlazeSwap documentation: https://docs.blazeswap.com
  2. FlareScan verified contracts: https://flarescan.com
  3. BlazeSwap GitHub: https://github.com/blazeswap/contracts

## How It Works

### Price Query Flow

```
KineticAdapter._get_reward_token_price(asset)
  ↓
Check if BlazeSwap router configured
  ↓
Initialize BlazeSwapPriceFeed
  ↓
Query router.getAmountsOut(rFLR, underlying_token, 1 rFLR)
  ↓
Return price: underlying_tokens_per_rFLR
  ↓
Use in distribution APR calculation
```

### Fallback Mechanism

If BlazeSwap router is unavailable:
1. Log warning
2. Return None from `_get_reward_token_price()`
3. Use `_estimate_reward_token_price()` with calibrated ratios
4. Continue with accurate calculations using fallback

## Usage

Once router address is verified, update `config/chains.yaml`:

```yaml
protocols:
  blazeswap:
    enabled: true
    router: "0x..."  # Actual BlazeSwap router address
```

The price feed will automatically:
- Query BlazeSwap for rFLR prices
- Use real-time prices in distribution APR calculations
- Fall back to estimated prices if router unavailable

## Testing

Current status:
- ✅ Structure implemented and tested
- ✅ Graceful fallback working
- ✅ Calculations accurate with fallback
- ⚠️ Need actual router address for live price queries

## Next Steps

1. **Find BlazeSwap Router Address**
   - Check BlazeSwap documentation
   - Search FlareScan for verified contracts
   - Verify router address on Flare network

2. **Update Configuration**
   - Add verified router address to `config/chains.yaml`
   - Test price queries with actual router

3. **Optional Enhancements**
   - Add caching for price queries
   - Implement pair contract direct queries as alternative
   - Add price feed health monitoring

