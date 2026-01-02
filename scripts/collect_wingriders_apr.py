#!/usr/bin/env python3
"""
WingRiders APR Collection Script

This script pulls pool data from WingRiders DEX on Cardano
and stores it in the `apr_snapshots` table.

Stores APR = feesAPR + stakingAPR + farmAPR:
- feesAPR: Trading fee APR (similar to HRA on other DEXs)
- stakingAPR: Additional yield from embedded ADA staking
- farmAPR: Yield farming rewards for LP token staking

Note: Boosting APR is NOT included as it requires WRT token staking.

WingRiders provides APR directly from their API, no calculation needed.
Collects pools with TVL > $10k (configurable).

Designed to be run daily via cron.

Cron example (10:10 AM server time):
    10 10 * * * cd /home/danladuke/Projects/DefiTracker && /home/danladuke/Projects/DefiTracker/venv/bin/python scripts/collect_wingriders_apr.py >> logs/wingriders_collection.log 2>&1
"""

import logging
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import yaml

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.collectors.chain_registry import ChainRegistry
from src.database.connection import DatabaseConnection
from src.database.queries import DatabaseQueries

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_config():
    """Load chain configuration from YAML."""
    config_path = PROJECT_ROOT / "config" / "chains.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def collect_and_store_wingriders():
    """Collect pool data from WingRiders and persist to the database."""
    logger.info("=" * 60)
    logger.info("Starting WingRiders pool collection")
    logger.info("Timestamp: %s", datetime.utcnow().isoformat())
    logger.info("=" * 60)

    db = None
    try:
        config = load_config()
        chain_config = config["chains"].get("cardano", {})
        protocol_config = chain_config.get("protocols", {}).get("wingriders", {})

        if not protocol_config.get("enabled", False):
            logger.warning("WingRiders is not enabled in configuration")
            return 1

        registry = ChainRegistry()
        chain_adapter = registry.get_chain("cardano")
        if not chain_adapter:
            logger.error("Cardano chain adapter not initialized or disabled")
            return 1

        # Get the WingRiders protocol adapter
        wingriders_adapter = chain_adapter.protocols.get("wingriders")
        if not wingriders_adapter:
            logger.error("WingRiders protocol adapter not found")
            return 1

        db = DatabaseConnection()
        queries = DatabaseQueries(db)

        blockchain_id = queries.get_or_create_blockchain(
            name="cardano",
            chain_id=chain_config.get("chain_id", 1),
            rpc_url=chain_config.get("rpc_url"),
        )
        protocol_id = queries.get_or_create_protocol(
            blockchain_id=blockchain_id,
            name="wingriders",
            api_url=protocol_config.get("graphql_url"),
        )

        # Get all pools meeting TVL threshold
        pools = wingriders_adapter.get_all_pools()
        timestamp = datetime.utcnow()

        logger.info("Found %d WingRiders pools with TVL >= $%s", 
                   len(pools), protocol_config.get("min_tvl_usd", 10000))

        inserted = 0
        farms_count = 0
        for pool in pools:
            # Use APR = fees + staking + farm
            # Boosting APR requires WRT token staking and is NOT included
            fees_apr = pool.fees_apr if pool.fees_apr else Decimal(0)
            staking_apr = pool.staking_apr if pool.staking_apr else Decimal(0)
            farm_apr = pool.farm_apr if pool.farm_apr else Decimal(0)
            total_apr = fees_apr + staking_apr + farm_apr

            asset_id = queries.get_or_create_asset(
                symbol=pool.pair, 
                name=f"WingRiders {pool.pair} ({pool.version})"
            )
            
            queries.insert_apr_snapshot(
                blockchain_id=blockchain_id,
                protocol_id=protocol_id,
                asset_id=asset_id,
                apr=total_apr,  # fees + staking + farm (excludes boost)
                timestamp=timestamp,
                yield_type='lp',  # WingRiders is a DEX - all pairs are liquidity pools
                tvl_usd=pool.tvl_usd,
            )
            inserted += 1
            if pool.has_farm:
                farms_count += 1
            
            tvl_str = f"${pool.tvl_usd:,.2f}" if pool.tvl_usd else "N/A"
            fees_str = f"{fees_apr:.2f}%" if fees_apr else "0.00%"
            staking_str = f"{staking_apr:.2f}%" if staking_apr else "0.00%"
            farm_str = f"{farm_apr:.2f}%" if farm_apr else "0.00%"
            total_str = f"{total_apr:.2f}%"
            
            if pool.has_farm:
                boost_str = f"{pool.boosting_apr:.2f}%" if pool.boosting_apr else "0.00%"
                logger.info("Stored %s (%s): APR=%s (Fees=%s + Stake=%s + Farm=%s), [Boost=%s not included], TVL=%s", 
                           pool.pair, pool.version, total_str, fees_str, staking_str, farm_str, boost_str, tvl_str)
            else:
                logger.info("Stored %s (%s): APR=%s (Fees=%s + Stake=%s), TVL=%s", 
                           pool.pair, pool.version, total_str, fees_str, staking_str, tvl_str)

        logger.info("WingRiders collection complete. Snapshots inserted: %s (%s with active farms)", 
                   inserted, farms_count)
        return 0

    except Exception as exc:
        logger.error("WingRiders collection failed: %s", exc, exc_info=True)
        return 1
    finally:
        if db:
            try:
                db.close_all()
            except Exception:
                pass


def main():
    exit_code = collect_and_store_wingriders()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

