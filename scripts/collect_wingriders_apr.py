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

Tracked Pools:
- Pools are tracked once discovered above TVL threshold
- Tracked pools are fetched even if they drop below threshold
- Pools only drop off after 30 consecutive days below threshold

Designed to be run daily via cron.

Cron example (10:10 AM server time):
    10 10 * * * cd /home/danladuke/Projects/DefiTracker && /home/danladuke/Projects/DefiTracker/venv/bin/python scripts/collect_wingriders_apr.py >> logs/wingriders_collection.log 2>&1
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

        # Check if we already collected today (EST)
        est = ZoneInfo("America/New_York")
        today_est = datetime.now(est).date()
        if queries.has_snapshots_for_date_est(protocol_id, today_est):
            logger.info("Data already collected for wingriders on %s (EST), skipping", today_est)
            return 0

        # Get TVL threshold from config
        min_tvl_ada = protocol_config.get("min_tvl_ada", 10000)

        # Get tracked pool pair names from database
        tracked_pools = queries.get_active_tracked_pools("wingriders")
        tracked_pairs = [p["pair_name"] for p in tracked_pools]
        logger.info("Found %d tracked pools in database", len(tracked_pairs))

        # Get all pools: those meeting threshold + tracked pools below threshold
        pools = wingriders_adapter.get_all_pools(tracked_pairs=tracked_pairs)
        timestamp = datetime.utcnow()

        logger.info("Found %d WingRiders pools total (above threshold + tracked)", len(pools))

        inserted = 0
        farms_count = 0
        pools_above_threshold = 0
        pools_below_threshold = 0

        for pool in pools:
            # Use APR = fees + staking + farm
            # Boosting APR requires WRT token staking and is NOT included
            fees_apr = pool.fees_apr if pool.fees_apr else Decimal(0)
            staking_apr = pool.staking_apr if pool.staking_apr else Decimal(0)
            farm_apr = pool.farm_apr if pool.farm_apr else Decimal(0)
            total_apr = fees_apr + staking_apr + farm_apr

            # 1-day APR: fees_apr is based on recent trading activity (daily snapshot)
            # For a daily view, include fees + staking + farm
            apr_1d = total_apr if total_apr else None

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
                version=pool.version,
                apr_1d=apr_1d,
                fee_apr=fees_apr,
                staking_apr=staking_apr,
                farm_apr=farm_apr,
                swap_fee_percent=pool.swap_fee_percent,
                volume_24h=pool.volume_24h_usd,
                fees_24h=pool.fees_24h_usd,
            )
            inserted += 1
            if pool.has_farm:
                farms_count += 1

            # Update tracked pools table
            # For WingRiders, use pair+version as the unique identifier
            pool_identifier = f"{pool.pair}-{pool.version}"
            above_threshold = pool.tvl_ada is not None and pool.tvl_ada >= min_tvl_ada
            queries.upsert_tracked_pool(
                protocol="wingriders",
                pool_identifier=pool_identifier,
                pair_name=pool.pair,
                version=pool.version,
                above_threshold=above_threshold
            )

            if above_threshold:
                pools_above_threshold += 1
            else:
                pools_below_threshold += 1

            tvl_str = f"${pool.tvl_usd:,.2f}" if pool.tvl_usd else "N/A"
            tvl_ada_str = f"{pool.tvl_ada:,.0f} ADA" if pool.tvl_ada else "N/A"
            fees_str = f"{fees_apr:.2f}%" if fees_apr else "0.00%"
            staking_str = f"{staking_apr:.2f}%" if staking_apr else "0.00%"
            farm_str = f"{farm_apr:.2f}%" if farm_apr else "0.00%"
            total_str = f"{total_apr:.2f}%"
            vol_str = f"${pool.volume_24h_usd:,.2f}" if pool.volume_24h_usd else "N/A"
            fees_24h_str = f"${pool.fees_24h_usd:,.2f}" if pool.fees_24h_usd else "N/A"
            threshold_indicator = "" if above_threshold else " [LOW TVL]"

            if pool.has_farm:
                boost_str = f"{pool.boosting_apr:.2f}%" if pool.boosting_apr else "0.00%"
                logger.info("Stored %s (%s)%s: APR(30d)=%s APR(1d)=%s (Fees=%s + Stake=%s + Farm=%s), [Boost=%s not included], TVL=%s (%s), Vol24h=%s",
                           pool.pair, pool.version, threshold_indicator, total_str, total_str, fees_str, staking_str, farm_str, boost_str, tvl_str, tvl_ada_str, vol_str)
            else:
                logger.info("Stored %s (%s)%s: APR(30d)=%s APR(1d)=%s (Fees=%s + Stake=%s), TVL=%s (%s), Vol24h=%s, Fees24h=%s",
                           pool.pair, pool.version, threshold_indicator, total_str, total_str, fees_str, staking_str, tvl_str, tvl_ada_str, vol_str, fees_24h_str)

        # Deactivate pools that have been below threshold for 30+ consecutive days
        deactivated = queries.deactivate_stale_pools("wingriders", grace_period_days=30)

        logger.info(
            "WingRiders collection complete. Snapshots: %s (%s with farms). "
            "Above threshold: %s, Below threshold: %s, Deactivated: %s",
            inserted, farms_count, pools_above_threshold, pools_below_threshold, deactivated
        )
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

