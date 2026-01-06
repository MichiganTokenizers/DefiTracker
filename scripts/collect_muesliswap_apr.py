#!/usr/bin/env python3
"""
MuesliSwap APR Collection Script

This script pulls pool data from MuesliSwap DEX on Cardano
and stores it in the `apr_snapshots` table.

Collects:
- APR (calculated from 24h trading fees / TVL * 365)
- TVL in ADA and USD
- 24h fees in USD
- 24h volume in USD

Collects pools with TVL >= 1000 ADA (configurable).

Designed to be run daily via cron.

Cron example (10:15 AM server time):
    15 10 * * * cd /home/danladuke/Projects/DefiTracker && /home/danladuke/Projects/DefiTracker/venv/bin/python scripts/collect_muesliswap_apr.py >> logs/muesliswap_collection.log 2>&1
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


def collect_and_store_muesliswap():
    """Collect pool data from MuesliSwap and persist to the database."""
    logger.info("=" * 60)
    logger.info("Starting MuesliSwap pool collection")
    logger.info("Timestamp: %s", datetime.utcnow().isoformat())
    logger.info("=" * 60)

    db = None
    try:
        config = load_config()
        chain_config = config["chains"].get("cardano", {})
        protocol_config = chain_config.get("protocols", {}).get("muesliswap", {})

        if not protocol_config.get("enabled", False):
            logger.warning("MuesliSwap is not enabled in configuration")
            return 1

        registry = ChainRegistry()
        chain_adapter = registry.get_chain("cardano")
        if not chain_adapter:
            logger.error("Cardano chain adapter not initialized or disabled")
            return 1

        # Get the MuesliSwap protocol adapter
        muesli_adapter = chain_adapter.protocols.get("muesliswap")
        if not muesli_adapter:
            logger.error("MuesliSwap protocol adapter not found")
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
            name="muesliswap",
            api_url=protocol_config.get("base_url"),
        )

        # Get all pools meeting TVL threshold
        pools = muesli_adapter.get_all_pools()
        timestamp = datetime.utcnow()

        min_tvl_ada = protocol_config.get("min_tvl_ada", 1000)
        logger.info("Found %d MuesliSwap pools with TVL >= %d ADA", 
                   len(pools), min_tvl_ada)

        inserted = 0
        for pool in pools:
            # Use APR calculated from 24h trading fees
            apr = pool.apr if pool.apr else Decimal(0)

            asset_id = queries.get_or_create_asset(
                symbol=pool.pair, 
                name=f"MuesliSwap {pool.pair}"
            )
            
            queries.insert_apr_snapshot(
                blockchain_id=blockchain_id,
                protocol_id=protocol_id,
                asset_id=asset_id,
                apr=apr,
                timestamp=timestamp,
                yield_type='lp',  # MuesliSwap is a DEX - all pairs are liquidity pools
                tvl_usd=pool.tvl_usd,
                fees_24h=pool.fees_24h_usd,
                volume_24h=pool.volume_24h_usd,
            )
            inserted += 1
            
            tvl_ada_str = f"{pool.tvl_ada:,.0f} ADA" if pool.tvl_ada else "N/A"
            tvl_usd_str = f"${pool.tvl_usd:,.2f}" if pool.tvl_usd else "N/A"
            apr_str = f"{apr:.2f}%" if apr else "N/A"
            fees_str = f"${pool.fees_24h_usd:,.2f}" if pool.fees_24h_usd else "N/A"
            vol_str = f"${pool.volume_24h_usd:,.0f}" if pool.volume_24h_usd else "N/A"
            logger.info("Stored %s: APR=%s, TVL=%s (%s), Fees24h=%s, Vol24h=%s", 
                       pool.pair, apr_str, tvl_ada_str, tvl_usd_str, fees_str, vol_str)

        logger.info("MuesliSwap collection complete. Snapshots inserted: %s", inserted)
        return 0

    except Exception as exc:
        logger.error("MuesliSwap collection failed: %s", exc, exc_info=True)
        return 1
    finally:
        if db:
            try:
                db.close_all()
            except Exception:
                pass


def main():
    exit_code = collect_and_store_muesliswap()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

