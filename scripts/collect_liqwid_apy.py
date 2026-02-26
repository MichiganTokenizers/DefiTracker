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


MINSWAP_BASE_URL = "https://api-mainnet-prod.minswap.org"

# Minswap ADA-pair LP assets for deriving token USD prices.
# Format: {farm_id}.{pool_id} from config/chains.yaml Minswap pairs.
# Token price = liquidity_a_currency / liquidity_b
# (same formula as MinswapAdapter.get_min_price)
MINSWAP_POOL_MAP = {
    'DJED': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c.a939812d08cfb6066e17d2914a7272c6b8c0197acdf68157d02c73649cc3efc0',
    'iUSD': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c.452089abb5bf8cc59b678a2cd7b9ee952346c6c0aa1cf27df324310a70d02fc3',
    'USDA': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c.ee5cfbc5b0dc10c873a0bcc69e49b9af21b899f59337a894874c6b596c2da136',
    'SHEN': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c.93a6e6b33626dd6e2cb52e446a80ee3b0c92b38cc158417b30a6d415e97652a1',
    'MIN': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c.82e2b1fd27a7712a1a9cf750dfbea1a5778611b20e06dd6a611df7a643f8cb75',
    'SNEK': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c.2ffadbb87144e875749122e0bbb9f535eeaa7f5660c6c4a91bcc4121e477f08d',
    'NIGHT': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c.e74c52975908a612d5ce68327040d449aae99f8b463bb6de046a1b23c5713169',
    'LQ': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c.6263e0101384dace4d7a8dadf0e6d45c8d43c8872604118ee82e3f2212934917',
    'IAG': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c.7b12f25ce8d6f424e1edbc8b61f0742fb13252605f31dc40373d6a245e8ec1d1',
    'USDM': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c.7dd6988c5a86693c76aeec1ea94afa41770be0de21a775ca7a2a1eabdb6a0171',
    # Wrapped tokens use equivalent Cardano-native token pools as price proxy
    'wanBTC': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c.63a3b8ee322ea31a931fd1902528809dc681bc650af21895533c9e98fa4bef2e',  # iBTC-ADA
    'wanETH': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c.562b9ff903fe8d9e1c980120a233051e7b1518cfc75eb9b4227f7710b670b6e9',  # iETH-ADA
}

# Stablecoins without dedicated Minswap ADA pools default to $1
STABLECOIN_DEFAULTS = {'wanUSDC', 'wanDAI'}


def fetch_token_prices() -> Dict[str, Decimal]:
    """Fetch current USD prices for Liqwid tokens from Minswap pool data.

    Derives prices from ADA-pair pool metrics on Minswap:
      token_price = liquidity_a_currency / liquidity_b
    ADA price is derived from the first successful pool response.
    """
    prices: Dict[str, Decimal] = {}
    session = requests.Session()
    session.headers.update({'User-Agent': 'defitracker/1.0'})

    for symbol, lp_asset in MINSWAP_POOL_MAP.items():
        try:
            resp = session.get(
                f"{MINSWAP_BASE_URL}/v1/pools/{lp_asset}/metrics",
                timeout=15
            )
            if not resp.ok:
                logger.warning(f"Minswap API returned {resp.status_code} for {symbol}")
                continue

            data = resp.json()
            liq_a_currency = data.get('liquidity_a_currency')
            liq_b = data.get('liquidity_b')

            if liq_a_currency and liq_b and float(liq_b) > 0:
                prices[symbol] = Decimal(str(liq_a_currency)) / Decimal(str(liq_b))

            # Derive ADA price from first successful pool response
            if 'ADA' not in prices:
                liq_a = data.get('liquidity_a')
                if liq_a_currency and liq_a and float(liq_a) > 0:
                    prices['ADA'] = Decimal(str(liq_a_currency)) / Decimal(str(liq_a))

        except Exception as e:
            logger.warning(f"Could not fetch Minswap price for {symbol}: {e}")
            continue

    # Default stablecoins without Minswap pools to $1
    for symbol in STABLECOIN_DEFAULTS:
        if symbol not in prices:
            prices[symbol] = Decimal('1.0')

    logger.info(f"Fetched prices for {len(prices)} tokens from Minswap")
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

