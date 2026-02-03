#!/usr/bin/env python3
"""
SundaeSwap APR Collection Script

This script pulls pool data from SundaeSwap DEX on Cardano
and stores it in the `apr_snapshots` table.

Collects:
- HRA (Historic Returns Annualized) - calculated from 24h LP fees / TVL * 365
- Farming APR - SUNDAE token rewards for eligible pools
- Total APR - HRA + Farming APR
- TVL in USD
- 24h fees in USD
- 24h volume in USD

APR Breakdown:
- Fee APR (HRA): Trading fees returned to liquidity providers
- Farming APR: SUNDAE token rewards distributed to eligible pools

Tracked Pools:
- Pools are tracked once discovered above TVL threshold
- Tracked pools are fetched even if not in popular list
- Pools only drop off after 30 consecutive days below threshold

Designed to be run daily via cron.

Cron example (10:05 AM server time):
    5 10 * * * cd /home/danladuke/Projects/DefiTracker && /home/danladuke/Projects/DefiTracker/venv/bin/python scripts/collect_sundaeswap_apr.py >> logs/sundaeswap_collection.log 2>&1
"""

import logging
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

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


def collect_and_store_sundaeswap():
    """Collect pool data from SundaeSwap and persist to the database."""
    logger.info("=" * 60)
    logger.info("Starting SundaeSwap pool collection")
    logger.info("Timestamp: %s", datetime.utcnow().isoformat())
    logger.info("=" * 60)

    db = None
    try:
        config = load_config()
        chain_config = config["chains"].get("cardano", {})
        protocol_config = chain_config.get("protocols", {}).get("sundaeswap", {})

        if not protocol_config.get("enabled", False):
            logger.warning("SundaeSwap is not enabled in configuration")
            return 1

        registry = ChainRegistry()
        chain_adapter = registry.get_chain("cardano")
        if not chain_adapter:
            logger.error("Cardano chain adapter not initialized or disabled")
            return 1

        # Get the SundaeSwap protocol adapter
        sundae_adapter = chain_adapter.protocols.get("sundaeswap")
        if not sundae_adapter:
            logger.error("SundaeSwap protocol adapter not found")
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
            name="sundaeswap",
            api_url=protocol_config.get("graphql_url"),
        )

        # Check if we already collected today (EST)
        est = ZoneInfo("America/New_York")
        today_est = datetime.now(est).date()
        if queries.has_snapshots_for_date_est(protocol_id, today_est):
            logger.info("Data already collected for sundaeswap on %s (EST), skipping", today_est)
            return 0

        # Get TVL threshold from config
        min_tvl_ada = protocol_config.get("min_tvl_ada", 10000)

        # Get tracked pool IDs from database
        tracked_pool_ids = queries.get_tracked_pool_ids("sundaeswap")
        logger.info("Found %d tracked pools in database", len(tracked_pool_ids))

        # Get all pools: popular + tracked pools not in popular list
        pools = sundae_adapter.get_all_pools(tracked_pool_ids=tracked_pool_ids)
        timestamp = datetime.utcnow()

        logger.info("Found %d SundaeSwap pools total (popular + tracked)", len(pools))

        inserted = 0
        farms_count = 0
        pools_above_threshold = 0
        pools_below_threshold = 0

        for pool in pools:
            # Use total APR (trading fees + farming rewards)
            apr = pool.total_apr if pool.total_apr else Decimal(0)

            # Calculate 1-day APR from fees only (HRA)
            # This represents the daily trading fee return, annualized
            apr_1d = pool.hra if pool.hra else None

            asset_id = queries.get_or_create_asset(
                symbol=pool.pair,
                name=f"SundaeSwap {pool.pair} ({pool.version})"
            )

            queries.insert_apr_snapshot(
                blockchain_id=blockchain_id,
                protocol_id=protocol_id,
                asset_id=asset_id,
                apr=apr,
                timestamp=timestamp,
                yield_type='lp',  # SundaeSwap is a DEX - all pairs are liquidity pools
                tvl_usd=pool.tvl_usd,
                fees_24h=pool.fees_24h_usd,
                volume_24h=pool.volume_24h_usd,
                version=pool.version,
                apr_1d=apr_1d,
                swap_fee_percent=pool.fee_percent,
            )
            inserted += 1
            if pool.has_farm:
                farms_count += 1

            # Update tracked pools table
            # A pool is above threshold if its TVL >= min_tvl_ada
            above_threshold = pool.tvl_ada is not None and pool.tvl_ada >= min_tvl_ada
            queries.upsert_tracked_pool(
                protocol="sundaeswap",
                pool_identifier=pool.pool_id,
                pair_name=pool.pair,
                version=pool.version,
                above_threshold=above_threshold
            )

            if above_threshold:
                pools_above_threshold += 1
            else:
                pools_below_threshold += 1

            # Format display strings
            tvl_str = f"${pool.tvl_usd:,.2f}" if pool.tvl_usd else "N/A"
            tvl_ada_str = f"{pool.tvl_ada:,.0f} ADA" if pool.tvl_ada else "N/A"
            total_str = f"{pool.total_apr:.2f}%" if pool.total_apr else "N/A"
            fee_str = f"{pool.hra:.2f}%" if pool.hra else "0%"
            farm_str = f"{pool.farming_apr:.2f}%" if pool.farming_apr else "0%"
            fees_24h_str = f"${pool.fees_24h_usd:,.2f}" if pool.fees_24h_usd else "N/A"
            vol_str = f"${pool.volume_24h_usd:,.0f}" if pool.volume_24h_usd else "N/A"

            # Log with APR breakdown
            farm_indicator = " [FARM]" if pool.has_farm else ""
            threshold_indicator = "" if above_threshold else " [LOW TVL]"
            logger.info(
                "Stored %s (%s)%s%s: Total=%s (Fees=%s + Farm=%s), TVL=%s (%s), Fees24h=%s, Vol24h=%s",
                pool.pair, pool.version, farm_indicator, threshold_indicator, total_str, fee_str, farm_str,
                tvl_str, tvl_ada_str, fees_24h_str, vol_str
            )

        # Deactivate pools that have been below threshold for 30+ consecutive days
        deactivated = queries.deactivate_stale_pools("sundaeswap", grace_period_days=30)

        logger.info(
            "SundaeSwap collection complete. Snapshots: %s (%s with farms). "
            "Above threshold: %s, Below threshold: %s, Deactivated: %s",
            inserted, farms_count, pools_above_threshold, pools_below_threshold, deactivated
        )
        return 0

    except Exception as exc:
        logger.error("SundaeSwap collection failed: %s", exc, exc_info=True)
        return 1
    finally:
        if db:
            try:
                db.close_all()
            except Exception:
                pass


def main():
    exit_code = collect_and_store_sundaeswap()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

