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

Collects pools with TVL > $10k (configurable).

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

        # Get all pools meeting TVL threshold
        pools = sundae_adapter.get_all_pools()
        timestamp = datetime.utcnow()

        logger.info("Found %d SundaeSwap pools with TVL >= $%s", 
                   len(pools), protocol_config.get("min_tvl_usd", 10000))

        inserted = 0
        farms_count = 0
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
            
            # Format display strings
            tvl_str = f"${pool.tvl_usd:,.2f}" if pool.tvl_usd else "N/A"
            total_str = f"{pool.total_apr:.2f}%" if pool.total_apr else "N/A"
            fee_str = f"{pool.hra:.2f}%" if pool.hra else "0%"
            farm_str = f"{pool.farming_apr:.2f}%" if pool.farming_apr else "0%"
            fees_24h_str = f"${pool.fees_24h_usd:,.2f}" if pool.fees_24h_usd else "N/A"
            vol_str = f"${pool.volume_24h_usd:,.0f}" if pool.volume_24h_usd else "N/A"
            
            # Log with APR breakdown
            farm_indicator = " [FARM]" if pool.has_farm else ""
            logger.info(
                "Stored %s (%s)%s: Total=%s (Fees=%s + Farm=%s), TVL=%s, Fees24h=%s, Vol24h=%s", 
                pool.pair, pool.version, farm_indicator, total_str, fee_str, farm_str, 
                tvl_str, fees_24h_str, vol_str
            )

        logger.info(
            "SundaeSwap collection complete. Snapshots inserted: %s (%s with farming rewards)", 
            inserted, farms_count
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

