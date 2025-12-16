#!/usr/bin/env python3
"""Test script for Kinetic adapter"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.adapters.flare.kinetic import KineticAdapter
from src.adapters.flare.chain_adapter import FlareChainAdapter
import yaml
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_kinetic_adapter():
    """Test Kinetic adapter initialization and basic functionality"""
    
    # Load config
    config_path = project_root / "config" / "chains.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    flare_config = config['chains']['flare']
    kinetic_config = flare_config['protocols']['kinetic']
    
    # Initialize Flare chain adapter
    print("Initializing Flare chain adapter...")
    flare_adapter = FlareChainAdapter(flare_config)
    
    # Get Kinetic adapter
    print("Getting Kinetic adapter...")
    kinetic_adapter = flare_adapter.get_protocol('kinetic')
    
    if not kinetic_adapter:
        print("❌ Kinetic adapter not found!")
        return False
    
    print("✓ Kinetic adapter initialized")
    
    # Test get_supported_assets
    print("\nTesting get_supported_assets()...")
    assets = kinetic_adapter.get_supported_assets()
    print(f"✓ Supported assets: {assets}")
    
    # Test get_supply_apr for each asset
    print("\nTesting get_supply_apr() (Method 1: Lens contract)...")
    for asset in assets:
        print(f"\n  Testing {asset}...")
        try:
            apr = kinetic_adapter.get_supply_apr(asset)
            if apr is not None:
                print(f"  ✓ {asset} APR: {apr}%")
            else:
                print(f"  ⚠ {asset} APR: Not available (contract may not be verified or method not available)")
        except Exception as e:
            print(f"  ❌ Error getting APR for {asset}: {e}")
    
    print("\n✓ Test completed!")
    return True


if __name__ == '__main__':
    try:
        test_kinetic_adapter()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

