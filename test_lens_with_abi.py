#!/usr/bin/env python3
"""Test Lens contract with extracted ABI"""
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from web3 import Web3
from decimal import Decimal

# Connect to Flare
w3 = Web3(Web3.HTTPProvider('https://flare-api.flare.network/ext/C/rpc'))

# Contract addresses
lens_address = "0x553e7b78812D69fA30242E7380417781125C7AC7"
iso_fxrp = "0xD1b7A5eFa9bd88F291F7A4563a8f6185c0249CB3"

print("Testing Lens contract with extracted ABI\n")
print("=" * 60)

# Try to load ABI from file
abi_file = project_root / "abis" / "lens_abi.json"
if abi_file.exists():
    print(f"✓ Found ABI file: {abi_file}")
    with open(abi_file, 'r') as f:
        lens_abi = json.load(f)
    
    functions = [item for item in lens_abi if item.get('type') == 'function']
    print(f"  Loaded {len(functions)} functions\n")
    
    # Create contract instance
    lens_contract = w3.eth.contract(
        address=Web3.to_checksum_address(lens_address),
        abi=lens_abi
    )
    
    # Try different function calls
    iso_address_checksum = Web3.to_checksum_address(iso_fxrp)
    
    print("Testing function calls:\n")
    
    # Test 1: getMarketMetadata - This is the key function!
    if any(f.get('name') == 'getMarketMetadata' for f in functions):
        print("1. Testing getMarketMetadata(address)...")
        try:
            result = lens_contract.functions.getMarketMetadata(iso_address_checksum).call()
            print(f"   ✓ SUCCESS! Got market metadata")
            
            # Result is a tuple/struct with named fields
            # Based on ABI: supplyRate is the second field (index 1)
            if isinstance(result, (list, tuple)) and len(result) >= 2:
                supply_rate = result[1]  # supplyRate is second field
                borrow_rate = result[2]  # borrowRate is third field
                total_supply = result[7]  # totalSupply
                total_underlying_supply = result[8]  # totalUnderlyingSupply
                
                print(f"\n   Market Data:")
                print(f"   - Supply Rate: {supply_rate}")
                print(f"   - Borrow Rate: {borrow_rate}")
                print(f"   - Total Supply: {total_supply}")
                print(f"   - Total Underlying Supply: {total_underlying_supply}")
                
                # Convert supply rate to APR
                # Supply rate is per block, need to convert to annual
                blocks_per_year = 365 * 24 * 60 * 60 / 2  # Flare has ~2 second blocks
                supply_rate_decimal = Decimal(supply_rate) / Decimal(10**18)
                apr = supply_rate_decimal * Decimal(blocks_per_year) * Decimal(100)
                
                print(f"\n   APR Calculation:")
                print(f"   - Supply Rate (decimal): {supply_rate_decimal:.10f}")
                print(f"   - Blocks per year: {blocks_per_year:,.0f}")
                print(f"   - APR: {apr:.4f}%")
                
        except Exception as e:
            print(f"   ✗ Failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Test 2: getMarketMetadataForAllMarkets
    if any(f.get('name') == 'getMarketMetadataForAllMarkets' for f in functions):
        print("\n2. Testing getMarketMetadataForAllMarkets()...")
        try:
            result = lens_contract.functions.getMarketMetadataForAllMarkets().call()
            print(f"   ✓ SUCCESS! Got metadata for {len(result)} markets")
            if len(result) > 0:
                print(f"   First market supply rate: {result[0][1]}")
        except Exception as e:
            print(f"   ✗ Failed: {e}")
    
    # List all available functions
    print("\n" + "=" * 60)
    print("Available functions in Lens contract:")
    rate_related = [f for f in functions if any(keyword in f.get('name', '').lower() 
                   for keyword in ['rate', 'supply', 'market', 'lens', 'get'])]
    for func in rate_related[:10]:
        inputs = ', '.join([inp.get('type', '') for inp in func.get('inputs', [])])
        print(f"  - {func.get('name')}({inputs})")
    
else:
    print(f"✗ ABI file not found: {abi_file}")
    print("\nPlease extract the ABI manually:")
    print(f"1. Visit: https://flarescan.com/address/{lens_address}#code")
    print("2. Copy the Contract ABI JSON")
    print(f"3. Save to: {abi_file}")
    print("\nSee MANUAL_ABI_EXTRACTION.md for detailed instructions")

