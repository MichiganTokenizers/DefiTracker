#!/usr/bin/env python3
"""
Kinetic APY Collection Script

This script collects APY data from Kinetic protocol and stores it in the database.
Designed to be run by cron daily.

Usage:
    python scripts/collect_kinetic_apy.py

Cron example (daily at midnight UTC):
    0 0 * * * cd /path/to/ffx && /path/to/venv/bin/python scripts/collect_kinetic_apy.py >> logs/kinetic_collection.log 2>&1
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from decimal import Decimal

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yaml
from src.adapters.flare.chain_adapter import FlareChainAdapter
from src.adapters.flare.blazeswap_price import BlazeSwapPriceFeed
from src.database.connection import DatabaseConnection
from src.database.queries import APYQueries
from src.database.models import KineticAPYSnapshot, PriceSnapshot
from web3 import Web3

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


def collect_prices(w3: Web3, config: dict, db_queries: APYQueries) -> dict:
    """Collect and store token prices from BlazeSwap"""
    logger.info("Collecting token prices from BlazeSwap...")
    
    blazeswap_config = config['chains']['flare']['protocols'].get('blazeswap', {})
    factory_address = blazeswap_config.get('factory')
    
    if not factory_address:
        logger.warning("BlazeSwap factory not configured, skipping price collection")
        return {}
    
    price_feed = BlazeSwapPriceFeed(w3, factory_address=factory_address)
    
    # WFLR address
    wflr_address = "0x1D80c49BbBCd1C0911346656B529DF9E5c2F783d"
    usdt0_address = "0xe7cd86e13AC4309349F30B3435a9d337750fC82D"
    
    prices = {}
    timestamp = datetime.utcnow()
    
    # Get WFLR/USDT0 price
    try:
        wflr_price = price_feed.get_price_with_decimals(
            token_in=wflr_address,
            token_out=usdt0_address,
            token_in_decimals=18,
            token_out_decimals=6
        )
        
        if wflr_price:
            # Find pair address for metadata
            pair_address = None
            try:
                pair_address = price_feed.factory_contract.functions.getPair(
                    Web3.to_checksum_address(wflr_address),
                    Web3.to_checksum_address(usdt0_address)
                ).call()
            except:
                pass
            
            # Store price snapshot
            snapshot = PriceSnapshot(
                token_symbol='WFLR',
                token_address=wflr_address,
                quote_token_symbol='USDT0',
                quote_token_address=usdt0_address,
                price_in_quote=wflr_price,
                source='blazeswap',
                pair_address=pair_address,
                timestamp=timestamp
            )
            
            snapshot_id = db_queries.insert_price_snapshot(snapshot)
            prices['WFLR'] = {'price': wflr_price, 'snapshot_id': snapshot_id}
            logger.info(f"WFLR price: {wflr_price:.8f} USDT0 (snapshot_id={snapshot_id})")
        else:
            logger.warning("Could not get WFLR price from BlazeSwap")
            
    except Exception as e:
        logger.error(f"Error collecting WFLR price: {e}")
    
    return prices


def collect_kinetic_apy(flare_adapter: FlareChainAdapter, db_queries: APYQueries, 
                        prices: dict) -> list:
    """Collect APY data from Kinetic protocol"""
    logger.info("Collecting Kinetic APY data...")
    
    kinetic = flare_adapter.get_protocol('kinetic')
    if not kinetic:
        logger.error("Kinetic adapter not found")
        return []
    
    timestamp = datetime.utcnow()
    snapshots = []
    
    # Get all supported tokens dynamically from adapter
    tokens = kinetic.get_supported_assets()
    logger.info(f"Collecting APY for {len(tokens)} tokens: {', '.join(tokens)}")
    
    for token in tokens:
        try:
            logger.info(f"Collecting APY for {token}...")
            
            # Get supply APY breakdown
            breakdown = kinetic.get_supply_apr_breakdown(token)
            
            if not breakdown:
                logger.warning(f"Could not get APY breakdown for {token}")
                continue
            
            # Get borrow APY
            borrow_apy = kinetic.get_borrow_apr(token)
            
            # Get or create asset in database
            # Use _all_tokens which includes all market tokens (Primary + ISO markets)
            token_config = kinetic._all_tokens.get(token, {})
            asset_id = db_queries.get_or_create_asset(
                symbol=token,
                contract_address=token_config.get('address'),
                decimals=token_config.get('decimals', 18)
            )
            
            # Get market type label for this token
            market_type = kinetic.get_market_label(token)
            
            # Get price snapshot ID (for WFLR used in distribution calculation)
            price_snapshot_id = prices.get('WFLR', {}).get('snapshot_id')
            
            # Create snapshot
            snapshot = KineticAPYSnapshot(
                asset_id=asset_id,
                asset_symbol=token,
                supply_apy=Decimal(str(breakdown['supply_apr'])),
                supply_distribution_apy=Decimal(str(breakdown['distribution_apr'])),
                total_supply_apy=Decimal(str(breakdown['total_apy'])),
                borrow_apy=Decimal(str(borrow_apy)) if borrow_apy else None,
                borrow_distribution_apy=None,  # Kinetic doesn't have borrow rewards currently
                price_snapshot_id=price_snapshot_id,
                timestamp=timestamp,
                market_type=market_type
            )
            
            # Insert snapshot
            snapshot_id = db_queries.insert_kinetic_apy_snapshot(snapshot)
            snapshot.snapshot_id = snapshot_id
            snapshots.append(snapshot)
            
            borrow_str = f"{borrow_apy:.4f}%" if borrow_apy else "N/A"
            logger.info(f"[{market_type}] {token}: Supply APY={breakdown['supply_apr']:.4f}%, "
                       f"Distribution APY={breakdown['distribution_apr']:.4f}%, "
                       f"Total={breakdown['total_apy']:.4f}%, "
                       f"Borrow APY={borrow_str}")
            
        except Exception as e:
            logger.error(f"Error collecting APY for {token}: {e}")
            continue
    
    return snapshots


def main():
    """Main collection function"""
    logger.info("=" * 60)
    logger.info("Starting Kinetic APY collection")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)
    
    try:
        # Load configuration
        config = load_config()
        flare_config = config['chains']['flare']
        
        # Initialize database
        db = DatabaseConnection()
        db_queries = APYQueries(db)
        
        # Initialize Web3
        w3 = Web3(Web3.HTTPProvider(flare_config['rpc_url']))
        if not w3.is_connected():
            logger.error("Could not connect to Flare RPC")
            return 1
        
        logger.info(f"Connected to Flare (block: {w3.eth.block_number})")
        
        # Initialize Flare adapter
        flare_adapter = FlareChainAdapter(flare_config)
        
        # Collect prices first
        prices = collect_prices(w3, config, db_queries)
        
        # Collect APY data
        snapshots = collect_kinetic_apy(flare_adapter, db_queries, prices)
        
        # Summary
        logger.info("=" * 60)
        logger.info("Collection complete!")
        logger.info(f"Price snapshots: {len(prices)}")
        logger.info(f"APY snapshots: {len(snapshots)}")
        logger.info("=" * 60)
        
        return 0
        
    except Exception as e:
        logger.error(f"Collection failed: {e}", exc_info=True)
        return 1
    finally:
        try:
            db.close_all()
        except:
            pass


if __name__ == '__main__':
    sys.exit(main())

