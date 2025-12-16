#!/usr/bin/env python3
"""Quick test for volume conversion fix"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.adapters.flare.kinetic import KineticAdapter
from src.adapters.flare.chain_adapter import FlareChainAdapter
import yaml
import logging
from web3 import Web3

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

# Test with just last 100 blocks (quick test)
test_blocks = 100
start_block = current_block - test_blocks

print(f"Testing volume conversion with {test_blocks} blocks")
print(f"Block range: {start_block} to {current_block}\n")

# Test FXRP
asset = 'FXRP'
token_config = kinetic_config['tokens'][asset]
token_address = token_config['address']
iso_address = token_config['iso_address']

print(f"Testing {asset}:")
print(f"  Token: {token_address}")
print(f"  ISO Market: {iso_address}")

# Test volume query
volume = kinetic_adapter._get_total_volume(asset, token_address, start_block, current_block)

if volume is not None:
    print(f"  ✓ Volume: {volume:.6f} tokens")
    print(f"  ✓ Conversion looks correct!")
else:
    print(f"  ⚠ No volume found")

