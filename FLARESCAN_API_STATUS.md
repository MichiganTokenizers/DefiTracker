# FlareScan API Status

## API Endpoint
- **URL**: `https://api.flarescan.com/api`
- **Documentation**: https://flarescan.com/documentation/api/etherscan-like/contracts
- **Free Tier**: 2 requests/second, 10,000 calls/day
- **No API Key Required**: Free tier doesn't need authentication

## Current Status

### ✅ Code Implementation
- Rate limiting implemented (2 req/sec)
- Proper error handling
- Fallback to contract page extraction

### ❌ API Access Issues
- **403 Forbidden**: CloudFront is blocking requests
- **202 Accepted**: Some requests return 202 (queued)
- Possible causes:
  - IP-based rate limiting/blocking
  - CloudFront WAF rules
  - Geographic restrictions
  - Too many requests from same IP

## Test Results

```bash
# Test command
python test_flarescan_api.py

# Results:
- Lens: 403 Forbidden
- Comptroller: 403 Forbidden  
- Unitroller: 403 Forbidden
- ISO FXRP: 403 Forbidden
```

## Alternative Approaches

### Option 1: Manual ABI Extraction
If contracts are verified on FlareScan:
1. Visit: https://flarescan.com/address/{CONTRACT_ADDRESS}#code
2. If verified, copy the ABI from the contract page
3. Save as JSON file in project

### Option 2: Check Contract Verification Status
Test URLs:
- Lens: https://flarescan.com/address/0x553e7b78812D69fA30242E7380417781125C7AC7#code
- Comptroller: https://flarescan.com/address/0x35aFf580e53d9834a3a0e21a50f97b942Aba8866#code
- Unitroller: https://flarescan.com/address/0x15F69897E6aEBE0463401345543C26d1Fd994abB#code
- ISO FXRP: https://flarescan.com/address/0xD1b7A5eFa9bd88F291F7A4563a8f6185c0249CB3#code

### Option 3: Use Different Network/VPN
- Try from different IP address
- Use VPN if geographic restrictions exist

### Option 4: Contact FlareScan Support
- Report 403 errors
- Ask about API access requirements
- Check if there are additional requirements

## What We Need for Method 1

To get Method 1 (Lens contract) working, we need:

1. **Lens Contract ABI** - Function signatures for:
   - `getMarketData(address)` or similar
   - `supplyRatePerBlock(address)` or similar
   - Any function that returns current supply rate

2. **Correct Function Calls** - Once we have the ABI:
   - Test calling Lens functions
   - Verify return values
   - Convert supply rate to APR

## Current Workaround

Since API access is blocked, we can:
1. **Continue with Method 2** (event-based) - This is working
2. **Manually extract ABIs** if contracts are verified
3. **Use minimal ABIs** we've created (may not have all functions)
4. **Try API from different location/IP** later

## Next Steps

1. ✅ Rate limiting code is ready
2. ⏳ Test API from different IP/location
3. ⏳ Check if contracts are verified on FlareScan website
4. ⏳ Manually extract ABIs if verified
5. ⏳ Test Lens contract calls once we have correct ABI

## Code Location

- **ABI Fetcher**: `src/adapters/flare/abi_fetcher.py`
- **Test Script**: `test_flarescan_api.py`
- **Usage**: `fetch_abi_from_flarescan(contract_address)`

The code is ready - we just need API access or manual ABI extraction.

