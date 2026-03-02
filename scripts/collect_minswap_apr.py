#!/usr/bin/env python3
"""
Minswap APR Collection Script

Dynamically discovers all Minswap pools above the TVL threshold (default 10K ADA)
and stores APR/TVL snapshots in the `apr_snapshots` table.

Discovery source: Minswap /defillama/yield-server endpoint (~150 pools).
Each qualifying pool is enriched with per-pool metrics (30-day APR, fees, volume).

Collects:
- Trading fee APR (30-day rolling average from API)
- 1-day APR (calculated from 24h fees / TVL)
- Farming APR (MIN rewards from yield server)
- TVL in USD and ADA
- 24h fees and volume

Tracked Pools:
- Pools are auto-discovered when above TVL threshold
- Previously tracked pools are included even if below threshold
- Pools only drop off after 30 consecutive days below threshold

Designed to be run daily via cron.

Cron example (10:00 AM server time):
    0 10 * * * cd /home/danladuke/Projects/DefiTracker && /home/danladuke/Projects/DefiTracker/venv/bin/python scripts/collect_minswap_apr.py >> logs/minswap_collection.log 2>&1
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


def collect_and_store_minswap():
    """Collect APRs, TVL, fees, and volume from Minswap and persist to the database."""
    logger.info("=" * 60)
    logger.info("Starting Minswap APR/TVL/Fees collection")
    logger.info("Timestamp: %s", datetime.utcnow().isoformat())
    logger.info("=" * 60)

    db = None
    try:
        config = load_config()
        chain_config = config["chains"].get("cardano", {})
        protocol_config = chain_config.get("protocols", {}).get("minswap", {})

        registry = ChainRegistry()
        chain_adapter = registry.get_chain("cardano")
        if not chain_adapter:
            logger.error("Cardano chain adapter not initialized or disabled")
            return 1

        # Get the Minswap protocol adapter directly for pool metrics
        minswap_adapter = chain_adapter.protocols.get("minswap")
        if not minswap_adapter:
            logger.error("Minswap protocol adapter not found")
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
            name="minswap",
            api_url=protocol_config.get("base_url"),
        )

        # Check if we already collected today (EST)
        est = ZoneInfo("America/New_York")
        today_est = datetime.now(est).date()
        if queries.has_snapshots_for_date_est(protocol_id, today_est):
            logger.info("Data already collected for minswap on %s (EST), skipping", today_est)
            return 0

        # Get TVL threshold from config
        min_tvl_ada = protocol_config.get("min_tvl_ada", 10000)

        # Get tracked pool IDs from database
        try:
            tracked_pool_ids = queries.get_tracked_pool_ids("minswap")
            logger.info("Found %d tracked pools in database", len(tracked_pool_ids))
        except Exception as e:
            logger.warning("Could not load tracked pools (table may not exist yet): %s", e)
            tracked_pool_ids = []

        # Discover all pools above threshold + tracked pools
        pools = minswap_adapter.get_all_pools(tracked_pool_ids=tracked_pool_ids)
        timestamp = datetime.utcnow()

        logger.info("Found %d Minswap pools total (discovered + tracked)", len(pools))

        inserted = 0
        pools_above_threshold = 0
        pools_below_threshold = 0

        for pool in pools:
            if pool.apr is None:
                logger.warning("Skipping %s due to missing APR", pool.pair)
                continue

            asset_id = queries.get_or_create_asset(symbol=pool.pair, name=pool.pair)
            queries.insert_apr_snapshot(
                blockchain_id=blockchain_id,
                protocol_id=protocol_id,
                asset_id=asset_id,
                apr=pool.apr,
                timestamp=timestamp,
                yield_type='lp',
                tvl_usd=pool.tvl_usd,
                fees_24h=pool.fees_24h,
                volume_24h=pool.volume_24h,
                apr_1d=pool.apr_1d,
                swap_fee_percent=pool.swap_fee_percent,
                version=pool.version,
            )
            inserted += 1

            # Update tracked pools table
            above_threshold = pool.tvl_ada is not None and pool.tvl_ada >= min_tvl_ada
            try:
                queries.upsert_tracked_pool(
                    protocol="minswap",
                    pool_identifier=pool.pool_id,
                    pair_name=pool.pair,
                    version=pool.version,
                    above_threshold=above_threshold
                )
            except Exception:
                pass  # tracked_pools table may not exist yet

            if above_threshold:
                pools_above_threshold += 1
            else:
                pools_below_threshold += 1

            # Format output strings
            tvl_str = f"${pool.tvl_usd:,.2f}" if pool.tvl_usd else "N/A"
            tvl_ada_str = f"{pool.tvl_ada:,.0f} ADA" if pool.tvl_ada else "N/A"
            fees_str = f"${pool.fees_24h:,.2f}" if pool.fees_24h else "N/A"
            apr_30d_str = f"{pool.apr:.2f}%" if pool.apr else "N/A"
            apr_1d_str = f"{pool.apr_1d:.2f}%" if pool.apr_1d else "N/A"

            # APR breakdown for logging
            fee_apr_str = f"{pool.trading_fee_apr_1d:.2f}%" if pool.trading_fee_apr_1d else "N/A"
            farm_apr_str = f"{pool.farming_apr_1d:.2f}%" if pool.farming_apr_1d else "0.00%"
            threshold_indicator = "" if above_threshold else " [LOW TVL]"

            if pool.farming_apr_1d:
                logger.info(
                    "Stored %s (%s)%s: APR(30d)=%s, APR(1d)=%s [Fees=%s + Farm=%s], TVL=%s (%s)",
                    pool.pair, pool.version, threshold_indicator, apr_30d_str, apr_1d_str,
                    fee_apr_str, farm_apr_str, tvl_str, tvl_ada_str
                )
            else:
                logger.info(
                    "Stored %s (%s)%s: APR(30d)=%s, APR(1d)=%s [Fees only], TVL=%s (%s), Fees24h=%s",
                    pool.pair, pool.version, threshold_indicator, apr_30d_str, apr_1d_str,
                    tvl_str, tvl_ada_str, fees_str
                )

        # Deactivate pools that have been below threshold for 30+ consecutive days
        try:
            deactivated = queries.deactivate_stale_pools("minswap", grace_period_days=30)
        except Exception:
            deactivated = 0  # tracked_pools table may not exist yet

        logger.info(
            "Minswap collection complete. Snapshots: %s. Above threshold: %s, Below threshold: %s, Deactivated: %s",
            inserted, pools_above_threshold, pools_below_threshold, deactivated
        )
        return 0

    except Exception as exc:
        logger.error("Minswap collection failed: %s", exc, exc_info=True)
        return 1
    finally:
        if db:
            try:
                db.close_all()
            except Exception:
                pass


def main():
    exit_code = collect_and_store_minswap()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

