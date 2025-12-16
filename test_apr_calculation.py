#!/usr/bin/env python3
"""Test full APR calculation with fixed volume conversion"""
import sys
from pathlib import Path
import time

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.adapters.flare.kinetic import KineticAdapter
from src.adapters.flare.chain_adapter import FlareChainAdapter
import yaml
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
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

# Test with last 1000 blocks (quick test)
test_blocks = 1000
start_block = current_block - test_blocks
blocks_per_day = 86400 / 2
test_days = test_blocks / blocks_per_day

print(f"Testing APR calculation with {test_blocks} blocks (~{test_days:.3f} days)")
print(f"Block range: {start_block} to {current_block}\n")

# Test FXRP
asset = 'FXRP'
token_config = kinetic_config['tokens'][asset]
token_address = token_config['address']

print(f"Testing {asset}:")
print("=" * 60)

# Get rewards
print("\n1. Querying rewards...")
start_time = time.time()
rewards = kinetic_adapter._get_rewards_paid(asset, token_address, start_block, current_block)
rewards_time = time.time() - start_time

if rewards is not None:
    print(f"   ✓ Rewards: {rewards:.6f} tokens")
    print(f"   ⏱ Time: {rewards_time:.2f} seconds")
else:
    print(f"   ⚠ No rewards found")
    rewards_time = 0

# Get volume
print("\n2. Querying volume...")
start_time = time.time()
volume = kinetic_adapter._get_total_volume(asset, token_address, start_block, current_block)
volume_time = time.time() - start_time

if volume is not None:
    print(f"   ✓ Volume: {volume:.6f} tokens")
    print(f"   ⏱ Time: {volume_time:.2f} seconds")
else:
    print(f"   ⚠ No volume found")
    volume_time = 0

# Calculate APR
if rewards is not None and volume is not None and volume > 0:
    print(f"\n3. Calculating APR...")
    apr = kinetic_adapter._calculate_apr_from_metrics(rewards, volume, test_days)
    total_time = rewards_time + volume_time
    
    print(f"   ✓ APR: {apr:.4f}%")
    print(f"   ⏱ Total query time: {total_time:.2f} seconds")
    print(f"\n   Formula: ({rewards:.6f} / {volume:.6f}) × (365 / {test_days:.3f}) × 100")
    print(f"   = ({rewards/volume:.10f}) × ({365/test_days:.2f}) × 100")
    print(f"   = {apr:.4f}%")
else:
    print(f"\n3. Cannot calculate APR:")
    if rewards is None:
        print(f"   - Missing rewards data")
    if volume is None or volume == 0:
        print(f"   - Missing or zero volume data")

