# Contract ABIs Directory

This directory contains manually extracted contract ABIs from FlareScan.

## Files to Add

After manually extracting ABIs from FlareScan, save them here with these names:

- `lens_abi.json` - Lens contract ABI
- `comptroller_abi.json` - Comptroller contract ABI  
- `unitroller_abi.json` - Unitroller contract ABI
- `iso_fxrp_abi.json` - ISO FXRP market contract ABI

## How to Extract

See `MANUAL_ABI_EXTRACTION.md` in the project root for detailed instructions.

## Quick Steps

1. Visit FlareScan contract page (see MANUAL_ABI_EXTRACTION.md for URLs)
2. If contract is verified, find the "Contract ABI" section
3. Copy the entire JSON array
4. Save to appropriate file in this directory

## Example

```json
[
  {
    "constant": true,
    "inputs": [{"name": "cToken", "type": "address"}],
    "name": "getMarketData",
    "outputs": [...],
    "type": "function"
  },
  ...
]
```

Once ABIs are saved here, the code will automatically use them instead of trying to fetch from the API.

