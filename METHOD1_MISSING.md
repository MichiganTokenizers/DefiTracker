# Method 1: Getting APR from Lens Contract - What We're Missing

## Current Status

### ✅ What We Have
- **Contract Addresses**: All correct from Kinetic documentation
  - Lens: `0x553e7b78812D69fA30242E7380417781125C7AC7`
  - Unitroller: `0x15F69897E6aEBE0463401345543C26d1Fd994abB`
  - Comptroller: `0x35aFf580e53d9834a3a0e21a50f97b942Aba8866`
  - ISO Markets: FXRP, USDT0, stXRP addresses
- **Web3 Connection**: Working
- **Code Structure**: Implementation ready, just needs correct function calls

### ❌ What's Not Working
- **Lens contract calls**: All function calls revert
- **Comptroller calls**: `getMarketData(address)` returns empty
- **ISO contract calls**: `supplyRatePerBlock()` reverts
- **FlareScan API**: Returns 403 (can't fetch ABIs automatically)

## What We're Missing

### 1. **Correct Function Signatures**
We've tried:
- `getMarketData(address)` on Lens/Comptroller → Empty result or revert
- `supplyRatePerBlock(address)` on Comptroller → Empty result
- `supplyRatePerBlock()` on ISO contract → Execution reverted

**What we need:**
- The actual function names and signatures for the Lens contract
- The correct way to call through the Unitroller proxy
- Whether functions need different parameters or calling conventions

### 2. **Lens Contract ABI**
- **Current**: Using minimal/guessed ABI based on standard Compound patterns
- **Problem**: Kinetic's Lens contract may have different interface
- **Solution needed**: 
  - Find Kinetic's GitHub repo with contract source
  - Check FlareScan for verified contract (if available)
  - Or reverse-engineer from successful calls

### 3. **Understanding Proxy Pattern**
- **Unitroller** is a proxy contract
- `markets(address)` works through Unitroller
- But rate functions don't work the same way
- **Need to understand**: How to call Comptroller functions through Unitroller proxy

### 4. **Alternative Approaches to Try**

#### Option A: Query Through Unitroller Proxy
Since `Unitroller.markets(address)` works, maybe rates are also accessible:
- Try: `Unitroller.supplyRatePerBlock(address)`
- Try: `Unitroller.getMarketData(address)`
- Use delegatecall pattern if needed

#### Option B: Direct Storage Access
- Supply rates might be stored in specific storage slots
- Could query storage directly if we know the slot numbers
- Requires understanding of contract storage layout

#### Option C: Interest Rate Model Contract
- ISO markets have Interest Rate Model contracts
- FXRP: `0x78a281a345925FbA8a6364b30280F68caD5f6018`
- USDT0: `0xF105aff328B4a8D00Eb6F7e992346294E5bF2938`
- These might expose supply rate functions

#### Option D: Use Lens Contract Differently
- Maybe Lens needs to be called with different parameters
- Or needs to be initialized/configured first
- Or requires specific access permissions

## Next Steps to Get Method 1 Working

### Priority 1: Find Lens Contract Source/ABI
1. **Search Kinetic GitHub**: Look for Lens contract source code
2. **Check FlareScan**: See if Lens contract is verified (view source)
3. **Contact Kinetic**: Ask for Lens contract interface/ABI
4. **Reverse Engineer**: Try common Compound Lens function names

### Priority 2: Try Alternative Contracts
1. **Interest Rate Model**: Query supply rate from IRM contracts
2. **Unitroller Proxy**: Try calling rate functions through Unitroller
3. **Storage Slots**: If we can find rate storage locations

### Priority 3: Test Different Function Signatures
Common Compound Lens functions to try:
- `cTokenMetadata(address)`
- `cTokenMetadataAll(address[])`
- `getAccountSnapshot(address, address)`
- `getMarketData(address)`
- `supplyRatePerBlock(address)`
- `borrowRatePerBlock(address)`

## Current Implementation

The code in `_get_apr_from_lens()` tries:
1. Comptroller.getMarketData(address) → Fails
2. Comptroller.supplyRatePerBlock(address) → Fails  
3. ISO contract.supplyRatePerBlock() → Fails
4. Lens contract (fallback) → Fails

All attempts result in "execution reverted" or empty results.

## What Would Make It Work

If we had:
1. ✅ **Lens contract ABI** → Could call functions correctly
2. ✅ **Correct function signatures** → Would know what to call
3. ✅ **Working example** → Could replicate successful calls
4. ✅ **Documentation** → Would know the intended API

## Recommendation

Since Method 2 (event-based) is working for volume and we're close on rewards, we could:
1. **Continue with Method 2** for now (it's functional)
2. **Research Method 1 in parallel** (find Lens ABI/source)
3. **Use Method 1 as enhancement** once we have the right interface

Method 1 would be faster (single call vs thousands of event queries) but requires the correct contract interface.

