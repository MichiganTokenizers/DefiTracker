#!/usr/bin/env python3
"""
Minswap APR Collection Script

This script pulls APR/APY data for configured Minswap pools (e.g., NIGHT-ADA)
and stores it in the `apr_snapshots` table.

Designed to be run daily via cron.

Cron example (10:00 AM server time):
    0 10 * * * cd /home/danladuke/Projects/DefiTracker && /home/danladuke/Projects/DefiTracker/venv/bin/python scripts/collect_minswap_apr.py >> logs/minswap_collection.log 2>&1
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


def collect_and_store_minswap():
    """Collect APRs from Minswap and persist to the database."""
    logger.info("=" * 60)
    logger.info("Starting Minswap APR collection")
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

        apr_results = chain_adapter.collect_aprs().get("minswap", {})
        timestamp = datetime.utcnow()

        inserted = 0
        for asset, apr in apr_results.items():
            if apr is None:
                logger.warning("Skipping %s due to missing APR", asset)
                continue

            asset_id = queries.get_or_create_asset(symbol=asset, name=asset)
            queries.insert_apr_snapshot(
                blockchain_id=blockchain_id,
                protocol_id=protocol_id,
                asset_id=asset_id,
                apr=Decimal(apr),
                timestamp=timestamp,
            )
            inserted += 1
            logger.info("Stored APR snapshot for %s: %s%%", asset, apr)

        logger.info("Minswap collection complete. Snapshots inserted: %s", inserted)
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

