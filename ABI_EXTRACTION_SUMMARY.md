# ABI Extraction Summary

## Current Status

✅ **Code Ready**: The ABI fetcher now supports loading ABIs from local files  
⏳ **Waiting**: Need to manually extract ABIs from FlareScan

## What's Been Set Up

1. **ABI Fetcher Updated** (`src/adapters/flare/abi_fetcher.py`):
   - Checks local `abis/` directory first
   - Falls back to API if local file not found
   - Falls back to minimal ABI if API fails

2. **Test Script Created** (`test_lens_with_abi.py`):
   - Tests Lens contract calls once ABI is available
   - Shows which functions are available
   - Tests common rate-related functions

3. **Documentation Created**:
   - `MANUAL_ABI_EXTRACTION.md` - Step-by-step guide
   - `abis/README.md` - Instructions for saving ABIs

## Next Steps

### 1. Extract ABIs Manually

Visit these FlareScan pages and extract the Contract ABI:

**Priority 1: Lens Contract** (most important for Method 1)
- URL: https://flarescan.com/address/0x553e7b78812D69fA30242E7380417781125C7AC7#code
- Save as: `abis/lens_abi.json`

**Priority 2: Comptroller**
- URL: https://flarescan.com/address/0x35aFf580e53d9834a3a0e21a50f97b942Aba8866#code
- Save as: `abis/comptroller_abi.json`

**Priority 3: Unitroller**
- URL: https://flarescan.com/address/0x15F69897E6aEBE0463401345543C26d1Fd994abB#code
- Save as: `abis/unitroller_abi.json`

**Priority 4: ISO FXRP**
- URL: https://flarescan.com/address/0xD1b7A5eFa9bd88F291F7A4563a8f6185c0249CB3#code
- Save as: `abis/iso_fxrp_abi.json`

### 2. Test After Extraction

Once you've saved the Lens ABI:

```bash
python3 test_lens_with_abi.py
```

This will:
- Load the ABI from `abis/lens_abi.json`
- Test calling Lens contract functions
- Show which functions are available
- Try to get supply rate data

### 3. Update Method 1 Implementation

Once we have the Lens ABI and know which functions work, we can:
- Update `_get_apr_from_lens()` to use the correct function calls
- Test getting supply rates
- Calculate APR from supply rate per block

## What We're Looking For

In the Lens ABI, we need functions that return:
- **Supply rate per block** - Current supply interest rate
- **Market data** - Including supply/borrow rates, totals, etc.

Common function names to look for:
- `getMarketData(address)` 
- `supplyRatePerBlock(address)`
- `cTokenMetadata(address)`
- `getAccountSnapshot(address, address)`

## Current Workaround

While waiting for ABIs:
- **Method 2** (event-based APR calculation) is working
- Volume conversion is fixed
- We can continue with Method 2 until Method 1 is ready

## Files Created

- `abis/` - Directory for extracted ABIs
- `abis/README.md` - Instructions
- `MANUAL_ABI_EXTRACTION.md` - Detailed extraction guide
- `test_lens_with_abi.py` - Test script
- `ABI_EXTRACTION_SUMMARY.md` - This file

