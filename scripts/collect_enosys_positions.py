#!/usr/bin/env python3
"""
Enosys DEX V3 Position Collection Script

This script collects NFT LP position data from Enosys DEX V3 on Flare
and stores pool and position snapshots for range analysis.

Collects:
- Pool state (current tick, liquidity, TVL)
- Individual NFT positions (range, liquidity, in-range status)
- Position metrics (range width, category, fee earnings)

Designed to be run periodically via cron (e.g., every 6 hours to match epochs).

Usage:
    python scripts/collect_enosys_positions.py

Cron example (every 6 hours, aligned with Enosys epochs):
    0 */6 * * * cd /home/danladuke/Projects/DefiTracker && /home/danladuke/Projects/DefiTracker/venv/bin/python scripts/collect_enosys_positions.py >> logs/enosys_collection.log 2>&1
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yaml
from web3 import Web3

from src.adapters.flare.chain_adapter import FlareChainAdapter
from src.adapters.flare.enosys import EnosysAdapter, EnosysPoolState, EnosysPosition
from src.database.connection import DatabaseConnection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    """Load chain configuration"""
    config_path = project_root / "config" / "chains.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def insert_pool_snapshot(conn, pool_state: EnosysPoolState, timestamp: datetime) -> int:
    """Insert a pool snapshot and return its ID."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO enosys_pool_snapshots (
                pool_address, token0_symbol, token1_symbol, fee_tier,
                current_tick, sqrt_price_x96, liquidity,
                tvl_token0, tvl_token1, tvl_usd,
                volume_24h_usd, fees_24h_usd,
                total_positions, active_positions,
                epoch_number, epoch_incentives, incentive_token_symbol,
                timestamp
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING snapshot_id
        """, (
            pool_state.pool_address,
            pool_state.token0_symbol,
            pool_state.token1_symbol,
            pool_state.fee_tier,
            pool_state.current_tick,
            str(pool_state.sqrt_price_x96) if pool_state.sqrt_price_x96 else None,
            str(pool_state.liquidity) if pool_state.liquidity else None,
            pool_state.tvl_token0,
            pool_state.tvl_token1,
            pool_state.tvl_usd,
            pool_state.volume_24h_usd,
            pool_state.fees_24h_usd,
            pool_state.total_positions,
            pool_state.active_positions,
            pool_state.epoch_number,
            pool_state.epoch_incentives,
            pool_state.incentive_token_symbol,
            timestamp
        ))
        snapshot_id = cur.fetchone()[0]
        conn.commit()
        return snapshot_id


def insert_position_snapshot(
    conn, 
    position: EnosysPosition, 
    pool_snapshot_id: int,
    timestamp: datetime
) -> int:
    """Insert a position snapshot and return its ID."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO enosys_position_snapshots (
                token_id, owner_address, pool_address,
                tick_lower, tick_upper,
                range_width_ticks, range_width_percent, range_category,
                liquidity, is_in_range,
                amount0, amount1, amount_usd,
                fees_token0, fees_token1, fees_usd,
                fees_24h_usd, fee_apr,
                epoch_number, time_in_range_pct, incentive_share, incentive_apr,
                total_apr,
                pool_snapshot_id, timestamp
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING snapshot_id
        """, (
            position.token_id,
            position.owner_address,
            position.pool_address,
            position.tick_lower,
            position.tick_upper,
            position.range_width_ticks,
            position.range_width_percent,
            position.range_category,
            str(position.liquidity) if position.liquidity else None,
            position.is_in_range,
            position.amount0,
            position.amount1,
            position.amount_usd,
            position.fees_token0,
            position.fees_token1,
            position.fees_usd,
            position.fees_24h_usd,
            position.fee_apr,
            position.epoch_number,
            position.time_in_range_pct,
            position.incentive_share,
            position.incentive_apr,
            position.total_apr,
            pool_snapshot_id,
            timestamp
        ))
        snapshot_id = cur.fetchone()[0]
        conn.commit()
        return snapshot_id


def collect_pool_and_positions(
    enosys_adapter: EnosysAdapter,
    pool_config: Dict,
    db_conn,
    timestamp: datetime
) -> Dict:
    """
    Collect data for a single pool and all its positions.
    
    Returns:
        Dict with collection statistics
    """
    pool_name = pool_config.get('symbol', pool_config.get('name', 'Unknown'))
    pool_address = pool_config.get('address', '')
    
    stats = {
        'pool_name': pool_name,
        'pool_snapshot_id': None,
        'total_positions': 0,
        'active_positions': 0,
        'narrow_positions': 0,
        'medium_positions': 0,
        'wide_positions': 0,
        'error': None
    }
    
    if not pool_address:
        stats['error'] = "Pool address not configured"
        logger.warning(f"Skipping {pool_name}: {stats['error']}")
        return stats
    
    try:
        # Get pool state
        logger.info(f"Fetching pool state for {pool_name} ({pool_address[:10]}...)")
        pool_state = enosys_adapter.get_pool_state(pool_address)
        
        if not pool_state:
            stats['error'] = "Could not fetch pool state"
            logger.warning(f"Skipping {pool_name}: {stats['error']}")
            return stats
        
        # Get all positions for this pool
        logger.info(f"Fetching positions for {pool_name}...")
        positions = enosys_adapter.get_positions_for_pool(pool_address)
        
        # Update pool state with position counts
        pool_state.total_positions = len(positions)
        pool_state.active_positions = sum(1 for p in positions if p.is_in_range)
        
        # Insert pool snapshot
        pool_snapshot_id = insert_pool_snapshot(db_conn, pool_state, timestamp)
        stats['pool_snapshot_id'] = pool_snapshot_id
        
        logger.info(
            f"Inserted pool snapshot for {pool_name}: tick={pool_state.current_tick}, "
            f"liquidity={pool_state.liquidity}, positions={pool_state.total_positions}"
        )
        
        # Insert position snapshots
        for position in positions:
            try:
                insert_position_snapshot(db_conn, position, pool_snapshot_id, timestamp)
                
                stats['total_positions'] += 1
                if position.is_in_range:
                    stats['active_positions'] += 1
                
                if position.range_category == 'narrow':
                    stats['narrow_positions'] += 1
                elif position.range_category == 'medium':
                    stats['medium_positions'] += 1
                else:
                    stats['wide_positions'] += 1
                    
            except Exception as e:
                logger.warning(f"Error inserting position {position.token_id}: {e}")
                continue
        
        logger.info(
            f"Inserted {stats['total_positions']} positions for {pool_name}: "
            f"narrow={stats['narrow_positions']}, medium={stats['medium_positions']}, "
            f"wide={stats['wide_positions']}, active={stats['active_positions']}"
        )
        
    except Exception as e:
        stats['error'] = str(e)
        logger.error(f"Error collecting {pool_name}: {e}")
    
    return stats


def main():
    """Main collection function"""
    logger.info("=" * 60)
    logger.info("Starting Enosys DEX V3 position collection")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)
    
    db = None
    
    try:
        # Load configuration
        config = load_config()
        flare_config = config['chains']['flare']
        enosys_config = flare_config.get('protocols', {}).get('enosys', {})
        
        if not enosys_config.get('enabled', False):
            logger.warning("Enosys is not enabled in configuration")
            return 1
        
        # Check for required contract addresses
        if not enosys_config.get('factory') or not enosys_config.get('position_manager'):
            logger.error(
                "Enosys contract addresses not configured. "
                "Please update config/chains.yaml with factory and position_manager addresses."
            )
            logger.info(
                "To find contract addresses:\n"
                "1. Visit https://dex.enosys.global\n"
                "2. Open browser dev tools (F12) -> Network tab\n"
                "3. Look for contract addresses in API calls or page source\n"
                "4. Or browse verified contracts on https://flarescan.com"
            )
            return 1
        
        # Initialize database
        db = DatabaseConnection()
        conn = db.get_connection()
        
        # Initialize Web3
        w3 = Web3(Web3.HTTPProvider(flare_config['rpc_url']))
        if not w3.is_connected():
            logger.error("Could not connect to Flare RPC")
            return 1
        
        logger.info(f"Connected to Flare (block: {w3.eth.block_number})")
        
        # Initialize Flare adapter to get Enosys
        flare_adapter = FlareChainAdapter(flare_config)
        enosys_adapter = flare_adapter.get_protocol('enosys')
        
        if not enosys_adapter:
            logger.error("Enosys adapter not initialized")
            return 1
        
        timestamp = datetime.utcnow()
        pools_config = enosys_config.get('pools', [])
        
        if not pools_config:
            logger.warning("No pools configured for Enosys")
            return 1
        
        logger.info(f"Collecting data for {len(pools_config)} configured pools...")
        
        # Collect data for each pool
        all_stats = []
        for pool_config in pools_config:
            stats = collect_pool_and_positions(
                enosys_adapter, pool_config, conn, timestamp
            )
            all_stats.append(stats)
        
        # Summary
        logger.info("=" * 60)
        logger.info("Collection complete!")
        
        total_pools = len(all_stats)
        successful_pools = sum(1 for s in all_stats if s['pool_snapshot_id'])
        total_positions = sum(s['total_positions'] for s in all_stats)
        active_positions = sum(s['active_positions'] for s in all_stats)
        narrow = sum(s['narrow_positions'] for s in all_stats)
        medium = sum(s['medium_positions'] for s in all_stats)
        wide = sum(s['wide_positions'] for s in all_stats)
        
        logger.info(f"Pools: {successful_pools}/{total_pools} successful")
        logger.info(f"Total positions: {total_positions}")
        logger.info(f"Active (in-range): {active_positions} ({active_positions/total_positions*100:.1f}% if total_positions else 0)")
        logger.info(f"By category: narrow={narrow}, medium={medium}, wide={wide}")
        
        # Log any errors
        errors = [s for s in all_stats if s.get('error')]
        if errors:
            logger.warning(f"Errors encountered for {len(errors)} pools:")
            for s in errors:
                logger.warning(f"  - {s['pool_name']}: {s['error']}")
        
        logger.info("=" * 60)
        
        return 0
        
    except Exception as e:
        logger.error(f"Collection failed: {e}", exc_info=True)
        return 1
    finally:
        if db:
            try:
                db.close_all()
            except:
                pass


if __name__ == '__main__':
    sys.exit(main())

