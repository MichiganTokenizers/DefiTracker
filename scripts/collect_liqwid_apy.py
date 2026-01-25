#!/usr/bin/env python3
"""
Liqwid APY Collection Script

This script collects APY data from Liqwid Finance protocol on Cardano
and stores it in the database. Designed to be run by cron daily.

Liqwid is a lending protocol similar to Kinetic, but on Cardano.

Usage:
    python scripts/collect_liqwid_apy.py

Cron example (daily at midnight UTC):
    0 0 * * * cd /path/to/DefiTracker && /path/to/venv/bin/python scripts/collect_liqwid_apy.py >> logs/liqwid_collection.log 2>&1
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict
from zoneinfo import ZoneInfo

import requests

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yaml
from src.adapters.cardano.chain_adapter import CardanoChainAdapter
from src.database.connection import DatabaseConnection
from src.database.queries import APYQueries
from src.database.models import LiqwidAPYSnapshot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database column NUMERIC(10, 4) can store max 999999.9999
# Cap extreme APY values to prevent overflow errors
MAX_APY_VALUE = Decimal('999999.9999')
MIN_APY_VALUE = Decimal('-999999.9999')


def cap_apy_value(value: Optional[Decimal], asset: str, field_name: str) -> Optional[Decimal]:
    """
    Cap APY value to prevent database overflow.
    
    Database columns are NUMERIC(10, 4) = max 999999.9999
    Logs a warning if capping occurs (indicates a calculation issue).
    
    Args:
        value: The APY value to cap
        asset: Asset symbol (for logging)
        field_name: Field name (for logging)
        
    Returns:
        Capped value, or None if input was None
    """
    if value is None:
        return None
    
    if value > MAX_APY_VALUE:
        logger.warning(
            f"APY overflow detected for {asset}.{field_name}: {value} capped to {MAX_APY_VALUE}"
        )
        return MAX_APY_VALUE
    
    if value < MIN_APY_VALUE:
        logger.warning(
            f"APY underflow detected for {asset}.{field_name}: {value} capped to {MIN_APY_VALUE}"
        )
        return MIN_APY_VALUE
    
    return value


def load_config():
    """Load chain configuration"""
    config_path = project_root / "config" / "chains.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


# CoinGecko token IDs for Liqwid assets
COINGECKO_IDS = {
    'ADA': 'cardano',
    'DJED': 'djed',
    'iUSD': 'indigo-protocol',
    'USDA': 'usd-coin',  # Stablecoin ~ $1
    'SHEN': 'shen',
    'MIN': 'minswap',
    'SNEK': 'snek',
    'NIGHT': 'tokenfi',
    'wanUSDC': 'usd-coin',  # Wrapped USDC ~ $1
    'wanDAI': 'dai',
    'wanBTC': 'bitcoin',
    'wanETH': 'ethereum',
    'LQ': 'liqwid-finance',
    'IAG': 'iagon',
}


def fetch_token_prices() -> Dict[str, Decimal]:
    """Fetch current USD prices for Liqwid tokens from CoinGecko."""
    # Get unique CoinGecko IDs
    ids = set(COINGECKO_IDS.values())
    ids_str = ','.join(ids)

    prices: Dict[str, Decimal] = {}

    try:
        response = requests.get(
            f'https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies=usd',
            timeout=15,
            headers={'User-Agent': 'defitracker/1.0'}
        )
        if response.ok:
            data = response.json()
            # Map back to our symbols
            for symbol, cg_id in COINGECKO_IDS.items():
                if cg_id in data and 'usd' in data[cg_id]:
                    prices[symbol] = Decimal(str(data[cg_id]['usd']))
                elif symbol in ['USDA', 'wanUSDC', 'wanDAI', 'iUSD']:
                    # Stablecoins default to $1
                    prices[symbol] = Decimal('1.0')

            logger.info(f"Fetched prices for {len(prices)} tokens from CoinGecko")
        else:
            logger.warning(f"CoinGecko API returned {response.status_code}")
    except Exception as e:
        logger.warning(f"Could not fetch token prices: {e}")

    return prices


def collect_liqwid_apy(cardano_adapter: CardanoChainAdapter, db_queries: APYQueries) -> List[LiqwidAPYSnapshot]:
    """Collect APY data from Liqwid Finance protocol"""
    logger.info("Collecting Liqwid APY data...")

    liqwid = cardano_adapter.get_protocol('liqwid')
    if not liqwid:
        logger.error("Liqwid adapter not found")
        return []

    # Fetch token prices for USD conversion
    prices = fetch_token_prices()

    timestamp = datetime.utcnow()
    snapshots = []

    # Get all supported markets
    markets = liqwid.get_supported_assets()
    logger.info(f"Collecting APY for {len(markets)} markets: {', '.join(markets)}")
    
    for market_symbol in markets:
        try:
            logger.info(f"Collecting APY for {market_symbol}...")
            
            # Get full market state (includes APYs and utilization)
            market_state = liqwid.get_market_state(market_symbol)
            
            if not market_state:
                # Fallback to individual APY queries
                supply_apy = liqwid.get_supply_apr(market_symbol)
                borrow_apy = liqwid.get_borrow_apr(market_symbol)
                
                if supply_apy is None and borrow_apy is None:
                    logger.warning(f"Could not get APY data for {market_symbol}")
                    continue
                
                market_state = {
                    'asset_symbol': market_symbol,
                    'market_id': None,
                    'supply_apy': supply_apy,
                    'lq_supply_apy': Decimal('0'),
                    'total_supply_apy': supply_apy,
                    'borrow_apy': borrow_apy,
                    'total_supply': None,
                    'total_borrows': None,
                    'utilization': None,
                    'available_liquidity': None,
                }
            
            # Get or create asset in database
            asset_id = db_queries.get_or_create_asset(
                symbol=market_symbol,
                name=market_state.get('asset_name'),
                decimals=market_state.get('decimals', 6)
            )
            
            # Cap APY values to prevent database overflow
            supply_apy = cap_apy_value(
                market_state.get('supply_apy'), 
                market_symbol, 
                'supply_apy'
            )
            lq_supply_apy = cap_apy_value(
                market_state.get('lq_supply_apy'),
                market_symbol,
                'lq_supply_apy'
            )
            total_supply_apy = cap_apy_value(
                market_state.get('total_supply_apy'),
                market_symbol,
                'total_supply_apy'
            )
            borrow_apy = cap_apy_value(
                market_state.get('borrow_apy'), 
                market_symbol, 
                'borrow_apy'
            )
            
            # Calculate USD values
            total_supply = market_state.get('total_supply')
            total_borrows = market_state.get('total_borrows')
            token_price = prices.get(market_symbol)

            total_supply_usd = None
            total_borrows_usd = None
            if token_price:
                if total_supply:
                    total_supply_usd = total_supply * token_price
                if total_borrows:
                    total_borrows_usd = total_borrows * token_price

            # Create snapshot
            snapshot = LiqwidAPYSnapshot(
                asset_id=asset_id,
                asset_symbol=market_symbol,
                market_id=market_state.get('market_id'),
                supply_apy=supply_apy,
                lq_supply_apy=lq_supply_apy,
                total_supply_apy=total_supply_apy,
                borrow_apy=borrow_apy,
                total_supply=total_supply,
                total_borrows=total_borrows,
                utilization_rate=market_state.get('utilization'),
                available_liquidity=market_state.get('available_liquidity'),
                total_supply_usd=total_supply_usd,
                total_borrows_usd=total_borrows_usd,
                token_price_usd=token_price,
                yield_type='supply',  # Primary view is supply (earn) side
                timestamp=timestamp
            )
            
            # Insert snapshot
            snapshot_id = db_queries.insert_liqwid_apy_snapshot(snapshot)
            snapshot.snapshot_id = snapshot_id
            snapshots.append(snapshot)
            
            supply_str = f"{supply_apy:.4f}%" if supply_apy else "N/A"
            lq_str = f"+{lq_supply_apy:.4f}% LQ" if lq_supply_apy and lq_supply_apy > 0 else ""
            total_str = f"{total_supply_apy:.4f}%" if total_supply_apy else "N/A"
            borrow_str = f"{borrow_apy:.4f}%" if borrow_apy else "N/A"
            utilization_str = f"{market_state.get('utilization', 0) * 100:.2f}%" if market_state.get('utilization') else "N/A"

            # Format volume data with USD
            supply_usd_str = f"${total_supply_usd:,.2f}" if total_supply_usd else "N/A"
            borrow_usd_str = f"${total_borrows_usd:,.2f}" if total_borrows_usd else "N/A"
            price_str = f"${token_price:.4f}" if token_price else "N/A"

            logger.info(
                f"{market_symbol}: Supply APY={supply_str} {lq_str} (Total: {total_str}), "
                f"Borrow APY={borrow_str}, "
                f"Utilization={utilization_str}, "
                f"TVL={supply_usd_str}, Borrowed={borrow_usd_str}, Price={price_str}"
            )
            
        except Exception as e:
            logger.error(f"Error collecting APY for {market_symbol}: {e}")
            continue
    
    return snapshots


def main():
    """Main collection function"""
    logger.info("=" * 60)
    logger.info("Starting Liqwid APY collection")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)
    
    try:
        # Load configuration
        config = load_config()
        cardano_config = config['chains']['cardano']
        
        # Check if Liqwid is enabled
        liqwid_config = cardano_config.get('protocols', {}).get('liqwid', {})
        if not liqwid_config.get('enabled', False):
            logger.warning("Liqwid protocol is not enabled in configuration")
            return 1
        
        # Initialize database
        db = DatabaseConnection()
        db_queries = APYQueries(db)

        # Check if we already collected today (EST)
        est = ZoneInfo("America/New_York")
        today_est = datetime.now(est).date()
        if db_queries.has_liqwid_snapshots_for_date_est(today_est):
            logger.info("Data already collected for liqwid on %s (EST), skipping", today_est)
            return 0

        # Initialize Cardano adapter
        cardano_adapter = CardanoChainAdapter(cardano_config)

        logger.info("Connected to Liqwid API")

        # Collect APY data
        snapshots = collect_liqwid_apy(cardano_adapter, db_queries)
        
        # Summary
        logger.info("=" * 60)
        logger.info("Collection complete!")
        logger.info(f"APY snapshots: {len(snapshots)}")
        
        if snapshots:
            avg_supply = sum(s.supply_apy for s in snapshots if s.supply_apy) / len([s for s in snapshots if s.supply_apy])
            logger.info(f"Average supply APY: {avg_supply:.4f}%")
        
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

