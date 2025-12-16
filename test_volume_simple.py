#!/usr/bin/env python3
"""Simple test for volume conversion"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.adapters.flare.kinetic import KineticAdapter
from src.adapters.flare.chain_adapter import FlareChainAdapter
import yaml
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load config
config_path = project_root / "config" / "chains.yaml"
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

flare_config = config['chains']['flare']
kinetic_config = flare_config['protocols']['kinetic']

# Initialize
flare_adapter = FlareChainAdapter(flare_config)
kinetic_adapter = flare_adapter.get_protocol('kinetic')

web3 = flare_adapter.get_web3_instance()
current_block = web3.eth.block_number

# Test with last 1000 blocks (should find some events)
test_blocks = 1000
start_block = current_block - test_blocks

print(f"Testing volume conversion with {test_blocks} blocks")
print(f"Block range: {start_block} to {current_block}\n")

# Test FXRP
asset = 'FXRP'
token_config = kinetic_config['tokens'][asset]
token_address = token_config['address']

print(f"Testing {asset}:")
volume = kinetic_adapter._get_total_volume(asset, token_address, start_block, current_block)

if volume is not None:
    print(f"  ✓ Volume: {volume:.6f} tokens")
    if 0.001 < volume < 1000000000:  # Reasonable range
        print(f"  ✓✓ Conversion looks correct! (reasonable value)")
    else:
        print(f"  ⚠ Value seems {'too large' if volume > 1000000000 else 'too small'}")
else:
    print(f"  ⚠ No volume found")

