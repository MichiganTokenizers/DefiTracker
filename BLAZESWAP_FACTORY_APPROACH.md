# BlazeSwap Price Feed - Factory-Based Approach

## Overview
Updated the BlazeSwap price feed to use **factory-based pair queries** instead of relying solely on a router contract. This approach is more reliable and aligns with how BlazeSwap contracts work.

## Contract Structure

Based on [BlazeSwap contracts](https://github.com/blazeswap/contracts):

1. **BlazeSwapFactory** or **BlazeSwapBaseFactory**
   - Creates and manages pair contracts
   - Has `getPair(tokenA, tokenB)` function
   - Returns pair contract address

2. **BlazeSwapBasePair** (or **BlazeSwapPair**)
   - Pair contract for token pairs
   - Has `getReserves()` function (returns reserve0, reserve1, blockTimestampLast)
   - Has `token0()` and `token1()` functions
   - Compatible with Uniswap V2 pair interface

3. **Router** (optional)
   - May or may not exist
   - Has `getAmountsOut()` if available
   - Used as fallback

## Implementation Approach

### Primary Method: Factory + Pair Queries

```
1. Factory.getPair(token0, token1) → pair_address
2. Pair.getReserves() → (reserve0, reserve1, timestamp)
3. Pair.token0() and Pair.token1() → identify token order
4. Calculate price: reserve1/reserve0 (adjusted for decimals and token order)
```

### Fallback Method: Router (if available)

```
1. Router.getAmountsOut(amountIn, [tokenIn, tokenOut]) → amounts[]
2. Extract amountOut from amounts[1]
3. Calculate price: amountOut / amountIn
```

## Price Calculation

For a pair with reserves:
- `reserve0`: Amount of token0 in pair
- `reserve1`: Amount of token1 in pair

Price of token_in in terms of token_out:
- If token_in == token0: `price = (reserve1 / 10^decimals_out) / (reserve0 / 10^decimals_in)`
- If token_in == token1: `price = (reserve0 / 10^decimals_out) / (reserve1 / 10^decimals_in)`

## Configuration

Update `config/chains.yaml`:

```yaml
protocols:
  blazeswap:
    enabled: true
    factory: "0x..."  # BlazeSwapFactory or BlazeSwapBaseFactory address
    router: "0x..."  # Optional: BlazeSwap router address (if exists)
```

## Finding Contract Addresses

### Factory Contract
The `BlazeSwapFactory` contract extends `BlazeSwapBaseFactory` and should have the standard `getPair(tokenA, tokenB)` function.

To find the deployed address:
1. Check BlazeSwap documentation/website: https://blaze-swap.com
2. Search FlareScan for verified "BlazeSwapFactory" contracts: https://flarescan.com
3. Check BlazeSwap GitHub for deployment addresses or documentation
4. Look for contracts deployed early in Flare network history
5. Check if BlazeSwap has a registry or known deployment addresses

**Contract Source**: [BlazeSwapFactory.sol](https://github.com/blazeswap/contracts/blob/main/contracts/core/BlazeSwapFactory.sol)

### Router Contract (Optional)
1. May not exist - BlazeSwap might not use a router
2. If it exists, search for "BlazeSwapRouter" or similar
3. Can use factory approach without router

## Advantages of Factory Approach

1. **More Reliable**: Pairs always exist if there's liquidity
2. **No Router Dependency**: Works even if router doesn't exist
3. **Direct Queries**: Simpler, fewer contract calls
4. **Standard Interface**: Compatible with Uniswap V2 style contracts

## Testing

Once factory address is found:

```python
from src.adapters.flare.blazeswap_price import BlazeSwapPriceFeed

price_feed = BlazeSwapPriceFeed(
    web3=w3,
    factory_address="0x...",  # BlazeSwapFactory address
    router_address="0x..."    # Optional
)

# Get rFLR price in USDT0
price = price_feed.get_price_with_decimals(
    token_in="0x1D80c49BbBCd1C0911346656B529DF9E5c2E78b7",  # rFLR
    token_out="0xe7cd86e13AC4309349F30B3435a9d337750fC82D",  # USDT0
    token_in_decimals=18,
    token_out_decimals=6
)
```

## Next Steps

1. **Find Factory Address**: Search FlareScan or BlazeSwap docs
2. **Update Config**: Add factory address to `config/chains.yaml`
3. **Test**: Verify price queries work with actual factory
4. **Monitor**: Ensure prices are accurate and up-to-date

