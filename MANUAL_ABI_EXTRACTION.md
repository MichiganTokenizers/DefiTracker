# Manual ABI Extraction Guide

Since FlareScan API and website are currently blocking automated requests, here's how to manually extract ABIs:

## Contract Addresses to Check

1. **Lens Contract**
   - Address: `0x553e7b78812D69fA30242E7380417781125C7AC7`
   - URL: https://flarescan.com/address/0x553e7b78812D69fA30242E7380417781125C7AC7#code

2. **Comptroller**
   - Address: `0x35aFf580e53d9834a3a0e21a50f97b942Aba8866`
   - URL: https://flarescan.com/address/0x35aFf580e53d9834a3a0e21a50f97b942Aba8866#code

3. **Unitroller**
   - Address: `0x15F69897E6aEBE0463401345543C26d1Fd994abB`
   - URL: https://flarescan.com/address/0x15F69897E6aEBE0463401345543C26d1Fd994abB#code

4. **ISO FXRP Market**
   - Address: `0xD1b7A5eFa9bd88F291F7A4563a8f6185c0249CB3`
   - URL: https://flarescan.com/address/0xD1b7A5eFa9bd88F291F7A4563a8f6185c0249CB3#code

## Steps to Extract ABI

### Method 1: From FlareScan Contract Page

1. Visit the contract address URL above
2. If the contract is verified, you'll see "Contract Source Code Verified" or similar
3. Look for a section labeled "Contract ABI" or "ABI"
4. Copy the entire ABI JSON
5. Save it to a file in the `abis/` directory:
   - `abis/lens_abi.json`
   - `abis/comptroller_abi.json`
   - `abis/unitroller_abi.json`
   - `abis/iso_fxrp_abi.json`

### Method 2: Using Browser Developer Tools

1. Open the contract page in your browser
2. Open Developer Tools (F12)
3. Go to Network tab
4. Refresh the page
5. Look for API calls to `/api` endpoint
6. Find the response that contains the ABI JSON
7. Copy and save it

### Method 3: Direct API Call (if you have access)

If you can access the API from your browser or a different network:

```bash
# Test from browser console or curl:
curl "https://api.flarescan.com/api?module=contract&action=getabi&address=0x553e7b78812D69fA30242E7380417781125C7AC7"
```

## What We're Looking For

For **Method 1** (Lens contract), we need functions like:
- `getMarketData(address)` - Returns market data including supply rate
- `supplyRatePerBlock(address)` - Returns current supply rate per block
- `cTokenMetadata(address)` - Returns cToken metadata
- Or similar functions that return supply/borrow rates

## After Extracting ABIs

Once you have the ABIs saved:

1. Update `src/adapters/flare/abi_fetcher.py` to load from local files:
   ```python
   def get_lens_abi() -> list:
       try:
           with open('abis/lens_abi.json', 'r') as f:
               return json.load(f)
       except FileNotFoundError:
           return get_minimal_lens_abi()
   ```

2. Test the Lens contract calls:
   ```python
   lens_abi = get_lens_abi()
   lens_contract = web3.eth.contract(address=lens_address, abi=lens_abi)
   # Try calling functions
   ```

## Quick Test Script

After extracting ABIs, run:

```bash
python3 test_lens_with_abi.py
```

This will test if we can successfully call Lens contract functions with the extracted ABI.

