#!/usr/bin/env python3
"""Test script for event-based APR calculation"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.adapters.flare.kinetic import KineticAdapter
from src.adapters.flare.chain_adapter import FlareChainAdapter
import yaml
import logging
import time
from decimal import Decimal

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_event_queries():
    """Test event-based APR calculation"""
    
    # Load config
    config_path = project_root / "config" / "chains.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    flare_config = config['chains']['flare']
    kinetic_config = flare_config['protocols']['kinetic']
    
    # Initialize Flare chain adapter
    print("=" * 60)
    print("Testing Event-Based APR Calculation")
    print("=" * 60)
    print("\n1. Initializing Flare chain adapter...")
    flare_adapter = FlareChainAdapter(flare_config)
    
    # Get Kinetic adapter
    print("2. Getting Kinetic adapter...")
    kinetic_adapter = flare_adapter.get_protocol('kinetic')
    
    if not kinetic_adapter:
        print("❌ Kinetic adapter not found!")
        return False
    
    print("✓ Kinetic adapter initialized\n")
    
    # Test assets
    assets = ['FXRP', 'USDT0', 'stXRP']
    
    # Test with 1 day lookback
    # 1 day = 86400 seconds / 2 seconds per block ≈ 43,200 blocks
    # This will require chunking into 30-block queries
    lookback_days = 1
    
    # Get current block to calculate block range
    web3 = flare_adapter.get_web3_instance()
    current_block = web3.eth.block_number
    blocks_per_day = 86400 / 2  # ~2 second blocks on Flare
    lookback_blocks = int(blocks_per_day * lookback_days)
    start_block = current_block - lookback_blocks
    
    print(f"\nBlock range: {start_block} to {current_block} ({lookback_blocks:,} blocks)")
    print(f"Time period: {lookback_days} day(s)")
    print(f"Estimated queries needed: {lookback_blocks / 30:.0f} (30 blocks per query)\n")
    
    for asset in assets:
        print(f"\n{'='*60}")
        print(f"Testing {asset}")
        print(f"{'='*60}")
        
        try:
            print(f"Querying events from last {lookback_days} day(s)...")
            
            # Call the internal methods directly to test with specific block range
            token_config = kinetic_config['tokens'].get(asset)
            if not token_config:
                print(f"⚠ Token config not found for {asset}")
                continue
            
            token_address = token_config['address']
            iso_address = token_config['iso_address']
            
            print(f"  Token: {token_address}")
            print(f"  ISO Market: {iso_address}")
            
            # Test rewards query with timing
            print(f"\n  Querying rewards...")
            start_time = time.time()
            rewards = kinetic_adapter._get_rewards_paid(asset, token_address, start_block, current_block)
            rewards_time = time.time() - start_time
            
            if rewards is not None:
                print(f"  ✓ Total rewards: {rewards:.6f} tokens")
            else:
                print(f"  ⚠ No rewards found (may be normal if no events in range)")
            print(f"  ⏱ Rewards query time: {rewards_time:.2f} seconds")
            
            # Test volume query with timing
            print(f"\n  Querying volume...")
            start_time = time.time()
            volume = kinetic_adapter._get_total_volume(asset, token_address, start_block, current_block)
            volume_time = time.time() - start_time
            
            if volume is not None:
                print(f"  ✓ Total volume: {volume:.6f} tokens")
            else:
                print(f"  ⚠ No volume found")
            print(f"  ⏱ Volume query time: {volume_time:.2f} seconds")
            
            # Calculate APR if we have both
            if rewards is not None and volume is not None and volume > 0:
                apr = kinetic_adapter._calculate_apr_from_metrics(rewards, volume, lookback_days)
                total_time = rewards_time + volume_time
                print(f"\n  ✓ Calculated APR: {apr:.4f}%")
                print(f"  ⏱ Total query time: {total_time:.2f} seconds")
            else:
                total_time = rewards_time + volume_time
                print(f"\n  ⚠ Cannot calculate APR (missing data)")
                print(f"  ⏱ Total query time: {total_time:.2f} seconds")
                    
        except Exception as e:
            print(f"❌ Error testing {asset}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("Test completed!")
    print(f"{'='*60}")
    return True


if __name__ == '__main__':
    try:
        test_event_queries()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

