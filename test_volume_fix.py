#!/usr/bin/env python3
"""Quick test for volume conversion fix"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from web3 import Web3
from eth_utils import keccak, to_bytes, to_hex
from decimal import Decimal

# Connect to Flare
w3 = Web3(Web3.HTTPProvider('https://flare-api.flare.network/ext/C/rpc'))

# FXRP ISO market
iso_fxrp = "0xD1b7A5eFa9bd88F291F7A4563a8f6185c0249CB3"
fxrp_decimals = 18

# Get a Mint event
mint_sig = "Mint(address,uint256,uint256)"
mint_hash = to_hex(keccak(to_bytes(text=mint_sig)))[:66]

current = w3.eth.block_number
# Query in chunks of 30 blocks to find a Mint event
print(f"Searching for Mint events (querying in 30-block chunks)...")
logs = []
start = current - 29  # Start with last 30 blocks

# Try up to 10 chunks (300 blocks) to find an event
for i in range(10):
    chunk_start = start - (i * 30)
    chunk_end = chunk_start + 29
    if chunk_start < 0:
        break
    try:
        chunk_logs = w3.eth.get_logs({
            'fromBlock': chunk_start,
            'toBlock': chunk_end,
            'address': Web3.to_checksum_address(iso_fxrp),
            'topics': [mint_hash]
        })
        if chunk_logs:
            logs = chunk_logs
            print(f"Found {len(logs)} Mint event(s) in blocks {chunk_start}-{chunk_end}")
            break
    except Exception as e:
        print(f"Error querying blocks {chunk_start}-{chunk_end}: {e}")
        break

if logs:
    log = logs[0]
    print(f"\nFound Mint event at block {log['blockNumber']}")
    print(f"Event data length: {len(log['data'])} bytes")
    
    if len(log['data']) >= 64:
        # First uint256: mintAmount (underlying token amount in wei)
        mint_amount_wei = int.from_bytes(log['data'][:32], 'big')
        # Second uint256: mintTokens (cToken amount)
        mint_tokens = int.from_bytes(log['data'][32:64], 'big')
        
        print(f"\nRaw values:")
        print(f"  mintAmount (wei): {mint_amount_wei}")
        print(f"  mintTokens: {mint_tokens}")
        
        # Convert mintAmount from wei to tokens
        mint_amount_tokens = Decimal(mint_amount_wei) / Decimal(10 ** fxrp_decimals)
        
        print(f"\nConverted values:")
        print(f"  mintAmount: {mint_amount_tokens:.6f} FXRP")
        print(f"  mintTokens: {mint_tokens / 10**8:.6f} cTokens (assuming 8 decimals)")
        
        # Verify with exchange rate
        exchange_rate_selector = "0x182df0f5"
        rate_result = w3.eth.call({
            'to': Web3.to_checksum_address(iso_fxrp),
            'data': exchange_rate_selector
        })
        
        if rate_result and len(rate_result) >= 32:
            exchange_rate = int.from_bytes(rate_result[:32], 'big')
            exchange_rate_decimal = Decimal(exchange_rate) / Decimal(10**18)
            
            print(f"\nExchange rate (raw): {exchange_rate}")
            print(f"Exchange rate (decimal): {exchange_rate_decimal:.10f}")
            
            # Convert cToken to underlying using exchange rate
            # Exchange rate format in Compound: exchangeRate = (underlyingAmount * 1e18) / cTokenAmount
            # So: underlyingAmount = (cTokenAmount * exchangeRate) / 1e18
            # 
            # mintTokens is in cToken's smallest unit (8 decimals for cTokens typically)
            # exchangeRate is scaled by 1e18
            # Result: underlyingAmount in underlying token's smallest unit (18 decimals for FXRP)
            
            # Calculate: (mintTokens * exchangeRate) / 1e18
            # exchangeRate is stored as: (underlyingAmount * 1e18) / cTokenAmount
            # So: underlyingAmount = (cTokenAmount * exchangeRate) / 1e18
            # 
            # mintTokens is in cToken's smallest unit (raw, no decimals applied yet)
            # After (mintTokens * exchangeRate) / 1e18, we get underlying in wei (18 decimals)
            underlying_wei = (Decimal(mint_tokens) * Decimal(exchange_rate)) / Decimal(10**18)
            # Convert from wei to tokens (divide by 10^18 for FXRP)
            underlying_tokens_from_ctoken = underlying_wei / Decimal(10 ** fxrp_decimals)
            
            # Actually, wait - if underlying_wei is already the result, and it's 60005.6655640041,
            # that means it's 60005.66... wei, which is 60005.66 / 10^18 = 0.00000000000006 tokens
            # That's way too small!
            
            # Let me check: maybe the exchange rate format is different
            # Or maybe mintTokens needs different handling
            # Try: treat mintTokens as having 8 decimals, then multiply by exchange rate
            # But exchange rate might already account for this...
            
            # Alternative: Maybe mintTokens needs to be treated as having 8 decimals first
            # cTokens typically have 8 decimals
            ctoken_decimals = 8
            mint_tokens_decimal = Decimal(mint_tokens) / Decimal(10 ** ctoken_decimals)
            # Then: underlying = cTokenAmount * (exchangeRate / 1e18)
            underlying_from_ctoken_v2 = mint_tokens_decimal * exchange_rate_decimal
            
            # Also try: maybe mintAmount is actually correct but we need to check its magnitude
            # If mintAmount is reasonable when divided properly, use it
            # Otherwise use mintTokens converted via exchange rate
            
            print(f"\n=== Analysis ===")
            print(f"\n1. Direct mintAmount conversion:")
            print(f"   Raw: {mint_amount_wei}")
            print(f"   / 10^{fxrp_decimals}: {mint_amount_tokens:.6f} FXRP")
            print(f"   Status: {'✓ Reasonable' if mint_amount_tokens < 1000000 else '✗ Too large!'}")
            
            print(f"\n2. mintTokens conversion via exchange rate (Method 1):")
            print(f"   mintTokens (raw): {mint_tokens}")
            print(f"   Exchange rate: {exchange_rate_decimal:.10f}")
            print(f"   Calculation: ({mint_tokens} * {exchange_rate}) / 1e18 = {underlying_wei}")
            print(f"   / 10^{fxrp_decimals}: {underlying_tokens_from_ctoken:.6f} FXRP")
            print(f"   Status: {'✓ Reasonable' if 0.001 < underlying_tokens_from_ctoken < 1000000 else '✗ Unreasonable'}")
            
            print(f"\n3. mintTokens conversion (Method 2 - treat as 8 decimals first):")
            print(f"   mintTokens as decimal: {mint_tokens_decimal:.6f} cTokens")
            print(f"   underlying = {mint_tokens_decimal:.6f} * {exchange_rate_decimal:.10f}")
            print(f"   = {underlying_from_ctoken_v2:.6f} FXRP")
            print(f"   Status: {'✓ Reasonable' if 0.001 < underlying_from_ctoken_v2 < 1000000 else '✗ Unreasonable'}")
            
            print(f"\n4. Recommendation:")
            if 0.001 < underlying_from_ctoken_v2 < 1000000:
                print(f"   ✓ USE Method 2: mintTokens (as cToken) * exchangeRate = {underlying_from_ctoken_v2:.6f} FXRP")
            elif 0.001 < underlying_tokens_from_ctoken < 1000000:
                print(f"   ✓ USE Method 1: (mintTokens * exchangeRate) / 1e18 = {underlying_tokens_from_ctoken:.6f} FXRP")
            elif mint_amount_tokens < 1000000:
                print(f"   ✓ USE: mintAmount directly = {mint_amount_tokens:.6f} FXRP")
            else:
                print(f"   ⚠ All values seem wrong - need to investigate further")
                print(f"   mintAmount might be in a different format or the event structure is different")
        
        print(f"\n✓ Correct conversion: mintAmount / 10^{fxrp_decimals} = {mint_amount_tokens:.6f} FXRP")
else:
    print("No Mint events found in last 30 blocks")

