# Finding BlazeSwapFactory Address on Flare

## Contract Structure

Based on the [BlazeSwapFactory contract](https://github.com/blazeswap/contracts/blob/main/contracts/core/BlazeSwapFactory.sol):

- `BlazeSwapFactory` extends `BlazeSwapBaseFactory`
- Should have standard `getPair(tokenA, tokenB)` function
- Creates `BlazeSwapPair` contracts

## Methods to Find Address

### 1. BlazeSwap Website/Documentation
- Visit https://blaze-swap.com
- Check documentation or "Contract Addresses" section
- Look for Flare network deployment addresses

### 2. FlareScan Search
- Go to https://flarescan.com
- Search for "BlazeSwapFactory" in verified contracts
- Filter by contract name or search recent deployments
- Look for contracts with "Factory" in the name

### 3. Check Contract Creation
- Find any BlazeSwap pair contract on FlareScan
- Check the "Creator" field - it should be the factory address
- Or check transaction that created the pair

### 4. GitHub/Community
- Check BlazeSwap GitHub issues or documentation
- Look for deployment addresses in README or docs
- Check community Discord/Telegram for addresses

### 5. Test with Known Pairs
If you know a BlazeSwap pair address:
```python
# Query the pair contract to find its factory
pair_contract = w3.eth.contract(address=pair_address, abi=pair_abi)
factory_address = pair_contract.functions.factory().call()
```

## Verification

Once you have a candidate address:

1. **Check it's a contract**: `w3.eth.get_code(address)` should return non-empty
2. **Verify it has getPair()**: Try calling `getPair(token0, token1)` with known tokens
3. **Check on FlareScan**: Verify the contract is verified and matches BlazeSwapFactory

## Testing

Once you have the address, test it:

```python
from src.adapters.flare.blazeswap_price import BlazeSwapPriceFeed

factory_address = "0x..."  # Found address
price_feed = BlazeSwapPriceFeed(w3, factory_address=factory_address)

# Test with rFLR/USDT0 pair
rflr = "0x1D80c49BbBCd1C0911346656B529DF9E5c2E78b7"
usdt0 = "0xe7cd86e13AC4309349F30B3435a9d337750fC82D"

price = price_feed.get_price_with_decimals(
    token_in=rflr,
    token_out=usdt0,
    token_in_decimals=18,
    token_out_decimals=6
)
```

## Current Status

- ✅ Implementation ready for factory-based queries
- ✅ ABI compatible with BlazeSwapFactory interface
- ⚠️ Need actual deployed factory address on Flare
- ⚠️ Once found, update `config/chains.yaml`

