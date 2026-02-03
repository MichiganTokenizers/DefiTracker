"""Database queries for APR/APY data"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta, date
from decimal import Decimal
from zoneinfo import ZoneInfo
from psycopg.rows import dict_row
import logging

from src.database.connection import DatabaseConnection
from src.database.models import APRSnapshot, LiqwidAPYSnapshot, PriceSnapshot

logger = logging.getLogger(__name__)


class DatabaseQueries:
    """Database query operations (legacy APR tracking)"""
    
    def __init__(self, db_connection: Optional[DatabaseConnection] = None):
        self.db = db_connection or DatabaseConnection()
    
    # ============================================
    # Blockchain Operations
    # ============================================
    
    def get_or_create_blockchain(self, name: str, chain_id: int, rpc_url: Optional[str] = None) -> int:
        """Get blockchain ID, create if doesn't exist"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT blockchain_id FROM blockchains WHERE name = %s",
                    (name,)
                )
                result = cur.fetchone()
                
                if result:
                    return result[0]
                
                cur.execute(
                    """INSERT INTO blockchains (name, chain_id, rpc_url)
                       VALUES (%s, %s, %s)
                       RETURNING blockchain_id""",
                    (name, chain_id, rpc_url)
                )
                blockchain_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Created blockchain: {name} (ID: {blockchain_id})")
                return blockchain_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Error getting/creating blockchain {name}: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    def get_blockchain_id(self, name: str) -> Optional[int]:
        """Get blockchain ID by name"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT blockchain_id FROM blockchains WHERE name = %s",
                    (name,)
                )
                result = cur.fetchone()
                return result[0] if result else None
        finally:
            self.db.return_connection(conn)
    
    def get_all_blockchains(self) -> List[Dict]:
        """Get all blockchains"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM blockchains WHERE enabled = TRUE ORDER BY name"
                )
                return [dict(row) for row in cur.fetchall()]
        finally:
            self.db.return_connection(conn)
    
    # ============================================
    # Protocol Operations
    # ============================================
    
    def get_or_create_protocol(self, blockchain_id: int, name: str, api_url: Optional[str] = None) -> int:
        """Get protocol ID, create if doesn't exist"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT protocol_id FROM protocols 
                       WHERE blockchain_id = %s AND name = %s""",
                    (blockchain_id, name)
                )
                result = cur.fetchone()
                
                if result:
                    return result[0]
                
                cur.execute(
                    """INSERT INTO protocols (blockchain_id, name, api_url)
                       VALUES (%s, %s, %s)
                       RETURNING protocol_id""",
                    (blockchain_id, name, api_url)
                )
                protocol_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Created protocol: {name} on blockchain {blockchain_id} (ID: {protocol_id})")
                return protocol_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Error getting/creating protocol {name}: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    def get_protocol_id(self, blockchain_id: int, protocol_name: str) -> Optional[int]:
        """Get protocol ID by blockchain and name"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT protocol_id FROM protocols 
                       WHERE blockchain_id = %s AND name = %s""",
                    (blockchain_id, protocol_name)
                )
                result = cur.fetchone()
                return result[0] if result else None
        finally:
            self.db.return_connection(conn)
    
    # ============================================
    # Asset Operations (legacy)
    # ============================================
    
    def get_or_create_asset(self, symbol: str, name: Optional[str] = None,
                           contract_address: Optional[str] = None,
                           decimals: int = 18) -> int:
        """Get asset ID, create if doesn't exist"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                if contract_address is None:
                    cur.execute(
                        """SELECT asset_id FROM assets
                           WHERE symbol = %s AND contract_address IS NULL""",
                        (symbol,)
                    )
                else:
                    cur.execute(
                        """SELECT asset_id FROM assets
                           WHERE symbol = %s AND contract_address = %s""",
                        (symbol, contract_address)
                    )
                result = cur.fetchone()
                
                if result:
                    return result[0]
                
                cur.execute(
                    """INSERT INTO assets (symbol, name, contract_address, decimals)
                       VALUES (%s, %s, %s, %s)
                       RETURNING asset_id""",
                    (symbol, name, contract_address, decimals)
                )
                asset_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Created asset: {symbol} (ID: {asset_id})")
                return asset_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Error getting/creating asset {symbol}: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    # ============================================
    # APR Snapshot Operations (legacy)
    # ============================================
    
    def insert_apr_snapshot(self, blockchain_id: int, protocol_id: int, 
                           asset_id: int, apr: Decimal, 
                           timestamp: Optional[datetime] = None,
                           yield_type: str = 'lp',
                           tvl_usd: Optional[Decimal] = None,
                           fees_24h: Optional[Decimal] = None,
                           volume_24h: Optional[Decimal] = None,
                           version: Optional[str] = None,
                           apr_1d: Optional[Decimal] = None,
                           fee_apr: Optional[Decimal] = None,
                           staking_apr: Optional[Decimal] = None,
                           farm_apr: Optional[Decimal] = None,
                           swap_fee_percent: Optional[Decimal] = None) -> int:
        """Insert a new APR snapshot
        
        Args:
            yield_type: Type of yield - 'lp' (liquidity pool), 'supply' (lending earn), 'borrow' (lending cost)
            tvl_usd: Total Value Locked in USD (for LPs: total pooled amount, for lending: supply/borrow value)
            fees_24h: Trading fees generated in last 24 hours (USD) - for DEX pools
            volume_24h: Trading volume in last 24 hours (USD) - for DEX pools
            version: Protocol version for LP pools (e.g., V1, V3 for SundaeSwap)
            apr_1d: Calculated 1-day APR (trading_fee_24h / TVL * 365 * 100) - for Minswap
            fee_apr: Trading fee APR component (percentage)
            staking_apr: Staking rewards APR component (e.g., embedded ADA staking)
            farm_apr: Farm/yield farming rewards APR component (token emissions)
            swap_fee_percent: Swap/trading fee percentage (e.g., 0.30 for 0.30%)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO apr_snapshots 
                       (blockchain_id, protocol_id, asset_id, apr, timestamp, yield_type, tvl_usd, fees_24h, volume_24h, version, apr_1d, fee_apr, staking_apr, farm_apr, swap_fee_percent)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING snapshot_id""",
                    (blockchain_id, protocol_id, asset_id, apr, timestamp, yield_type, tvl_usd, fees_24h, volume_24h, version, apr_1d, fee_apr, staking_apr, farm_apr, swap_fee_percent)
                )
                snapshot_id = cur.fetchone()[0]
                conn.commit()
                return snapshot_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Error inserting APR snapshot: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    def has_snapshots_for_date_est(self, protocol_id: int, date_est: date) -> bool:
        """Check if any apr_snapshots exist for protocol on given EST date.

        Converts EST date boundaries to UTC for query since timestamps are stored in UTC.
        EST midnight = UTC 05:00 (or 04:00 during DST).

        Args:
            protocol_id: The protocol ID to check
            date_est: The EST date to check for snapshots

        Returns:
            True if at least one snapshot exists for that date, False otherwise
        """
        est = ZoneInfo("America/New_York")

        # Create datetime at start of day in EST, then convert to UTC
        start_of_day_est = datetime(date_est.year, date_est.month, date_est.day, tzinfo=est)
        end_of_day_est = start_of_day_est + timedelta(days=1)

        # Convert to UTC for database query
        start_utc = start_of_day_est.astimezone(ZoneInfo("UTC"))
        end_utc = end_of_day_est.astimezone(ZoneInfo("UTC"))

        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT EXISTS(
                        SELECT 1 FROM apr_snapshots
                        WHERE protocol_id = %s
                          AND timestamp >= %s
                          AND timestamp < %s
                    )""",
                    (protocol_id, start_utc, end_utc)
                )
                result = cur.fetchone()
                return result[0] if result else False
        finally:
            self.db.return_connection(conn)

    # ============================================
    # Tracked Pools Operations
    # ============================================

    def get_active_tracked_pools(self, protocol: str) -> List[Dict]:
        """Get all active tracked pools for a protocol.

        Args:
            protocol: Protocol name (e.g., 'sundaeswap', 'wingriders')

        Returns:
            List of tracked pool dicts with pool_identifier, pair_name, version
        """
        conn = self.db.get_connection()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """SELECT id, pool_identifier, pair_name, version,
                              first_tracked_date, last_above_threshold_date,
                              consecutive_days_below
                       FROM tracked_pools
                       WHERE protocol = %s AND is_active = TRUE
                       ORDER BY pair_name""",
                    (protocol,)
                )
                return [dict(row) for row in cur.fetchall()]
        finally:
            self.db.return_connection(conn)

    def upsert_tracked_pool(
        self,
        protocol: str,
        pool_identifier: str,
        pair_name: str,
        version: Optional[str] = None,
        above_threshold: bool = True
    ) -> int:
        """Add or update a tracked pool.

        If pool exists and above_threshold=True, resets consecutive_days_below to 0.
        If pool exists and above_threshold=False, increments consecutive_days_below.

        Args:
            protocol: Protocol name
            pool_identifier: Unique pool ID for this protocol
            pair_name: Display name (e.g., 'iUSD-ADA')
            version: Pool version (e.g., 'V3')
            above_threshold: Whether pool TVL is currently above threshold

        Returns:
            Tracked pool ID
        """
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                today = date.today()

                if above_threshold:
                    # Pool is above threshold - reset counter, update last_above date
                    cur.execute(
                        """INSERT INTO tracked_pools
                           (protocol, pool_identifier, pair_name, version,
                            last_above_threshold_date, consecutive_days_below, is_active)
                           VALUES (%s, %s, %s, %s, %s, 0, TRUE)
                           ON CONFLICT (protocol, pool_identifier)
                           DO UPDATE SET
                               pair_name = EXCLUDED.pair_name,
                               version = EXCLUDED.version,
                               last_above_threshold_date = EXCLUDED.last_above_threshold_date,
                               consecutive_days_below = 0,
                               is_active = TRUE,
                               updated_at = CURRENT_TIMESTAMP
                           RETURNING id""",
                        (protocol, pool_identifier, pair_name, version, today)
                    )
                else:
                    # Pool is below threshold - increment counter
                    cur.execute(
                        """INSERT INTO tracked_pools
                           (protocol, pool_identifier, pair_name, version,
                            consecutive_days_below, is_active)
                           VALUES (%s, %s, %s, %s, 1, TRUE)
                           ON CONFLICT (protocol, pool_identifier)
                           DO UPDATE SET
                               consecutive_days_below = tracked_pools.consecutive_days_below + 1,
                               updated_at = CURRENT_TIMESTAMP
                           RETURNING id""",
                        (protocol, pool_identifier, pair_name, version)
                    )

                pool_id = cur.fetchone()[0]
                conn.commit()
                return pool_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Error upserting tracked pool {pair_name}: {e}")
            raise
        finally:
            self.db.return_connection(conn)

    def deactivate_stale_pools(self, protocol: str, grace_period_days: int = 7) -> int:
        """Deactivate pools that have been below threshold for too long.

        Args:
            protocol: Protocol name
            grace_period_days: Number of consecutive days below threshold before deactivation

        Returns:
            Number of pools deactivated
        """
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE tracked_pools
                       SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                       WHERE protocol = %s
                         AND is_active = TRUE
                         AND consecutive_days_below >= %s
                       RETURNING id, pair_name""",
                    (protocol, grace_period_days)
                )
                deactivated = cur.fetchall()
                conn.commit()

                for pool_id, pair_name in deactivated:
                    logger.info(f"Deactivated tracked pool {pair_name} (id={pool_id}) after {grace_period_days} days below threshold")

                return len(deactivated)
        except Exception as e:
            conn.rollback()
            logger.error(f"Error deactivating stale pools: {e}")
            raise
        finally:
            self.db.return_connection(conn)

    def get_tracked_pool_ids(self, protocol: str) -> List[str]:
        """Get just the pool identifiers for active tracked pools.

        Args:
            protocol: Protocol name

        Returns:
            List of pool identifier strings
        """
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT pool_identifier
                       FROM tracked_pools
                       WHERE protocol = %s AND is_active = TRUE""",
                    (protocol,)
                )
                return [row[0] for row in cur.fetchall()]
        finally:
            self.db.return_connection(conn)

    def get_latest_aprs(self, blockchain_name: Optional[str] = None,
                       protocol_name: Optional[str] = None,
                       asset_symbol: Optional[str] = None) -> List[Dict]:
        """Get latest APR values with optional filters"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                query = """
                    SELECT
                        b.name AS blockchain,
                        p.name AS protocol,
                        a.symbol AS asset,
                        s.apr,
                        s.timestamp
                    FROM apr_snapshots s
                    JOIN blockchains b ON s.blockchain_id = b.blockchain_id
                    JOIN protocols p ON s.protocol_id = p.protocol_id
                    JOIN assets a ON s.asset_id = a.asset_id
                    WHERE s.timestamp = (
                        SELECT MAX(timestamp)
                        FROM apr_snapshots
                        WHERE blockchain_id = s.blockchain_id
                          AND protocol_id = s.protocol_id
                          AND asset_id = s.asset_id
                    )
                """
                
                conditions = []
                params = []
                
                if blockchain_name:
                    conditions.append("b.name = %s")
                    params.append(blockchain_name)
                
                if protocol_name:
                    conditions.append("p.name = %s")
                    params.append(protocol_name)
                
                if asset_symbol:
                    conditions.append("a.symbol = %s")
                    params.append(asset_symbol)
                
                if conditions:
                    query += " AND " + " AND ".join(conditions)
                
                query += " ORDER BY b.name, p.name, a.symbol"
                
                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]
        finally:
            self.db.return_connection(conn)


class APYQueries:
    """Query class for APY-related database operations"""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def has_liqwid_snapshots_for_date_est(self, date_est: date) -> bool:
        """Check if any liqwid_apy_snapshots exist for the given EST date.

        Converts EST date boundaries to UTC for query since timestamps are stored in UTC.

        Args:
            date_est: The EST date to check for snapshots

        Returns:
            True if at least one snapshot exists for that date, False otherwise
        """
        est = ZoneInfo("America/New_York")

        # Create datetime at start of day in EST, then convert to UTC
        start_of_day_est = datetime(date_est.year, date_est.month, date_est.day, tzinfo=est)
        end_of_day_est = start_of_day_est + timedelta(days=1)

        # Convert to UTC for database query
        start_utc = start_of_day_est.astimezone(ZoneInfo("UTC"))
        end_utc = end_of_day_est.astimezone(ZoneInfo("UTC"))

        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT EXISTS(
                        SELECT 1 FROM liqwid_apy_snapshots
                        WHERE timestamp >= %s
                          AND timestamp < %s
                    )""",
                    (start_utc, end_utc)
                )
                result = cur.fetchone()
                return result[0] if result else False
        finally:
            self.db.return_connection(conn)

    # ============================================
    # Asset operations
    # ============================================
    
    def get_or_create_asset(self, symbol: str, contract_address: Optional[str] = None,
                            name: Optional[str] = None, decimals: int = 18) -> int:
        """Get asset_id or create new asset if not exists"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                # Try to find existing asset
                if contract_address is None:
                    cur.execute("""
                        SELECT asset_id FROM assets
                        WHERE symbol = %s AND contract_address IS NULL
                    """, (symbol,))
                else:
                    cur.execute("""
                        SELECT asset_id FROM assets
                        WHERE symbol = %s AND contract_address = %s
                    """, (symbol, contract_address))

                result = cur.fetchone()
                if result:
                    return result[0]
                
                # Create new asset
                cur.execute("""
                    INSERT INTO assets (symbol, name, contract_address, decimals)
                    VALUES (%s, %s, %s, %s)
                    RETURNING asset_id
                """, (symbol, name or symbol, contract_address, decimals))
                
                asset_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Created new asset: {symbol} (id={asset_id})")
                return asset_id
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error getting/creating asset {symbol}: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    # ============================================
    # Price snapshot operations
    # ============================================
    
    def insert_price_snapshot(self, snapshot: PriceSnapshot) -> int:
        """Insert a price snapshot and return its ID"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO price_snapshots (
                        token_symbol, token_address, price_usd,
                        quote_token_symbol, quote_token_address, price_in_quote,
                        source, pair_address, reserve_token, reserve_quote,
                        timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING snapshot_id
                """, (
                    snapshot.token_symbol,
                    snapshot.token_address,
                    snapshot.price_usd,
                    snapshot.quote_token_symbol,
                    snapshot.quote_token_address,
                    snapshot.price_in_quote,
                    snapshot.source,
                    snapshot.pair_address,
                    snapshot.reserve_token,
                    snapshot.reserve_quote,
                    snapshot.timestamp or datetime.utcnow()
                ))
                
                snapshot_id = cur.fetchone()[0]
                conn.commit()
                logger.debug(f"Inserted price snapshot: {snapshot.token_symbol} (id={snapshot_id})")
                return snapshot_id
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error inserting price snapshot: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    def get_latest_price(self, token_symbol: str, source: Optional[str] = None) -> Optional[PriceSnapshot]:
        """Get the latest price for a token"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                if source:
                    cur.execute("""
                        SELECT snapshot_id, token_symbol, token_address, price_usd,
                               quote_token_symbol, quote_token_address, price_in_quote,
                               source, pair_address, reserve_token, reserve_quote, timestamp
                        FROM price_snapshots
                        WHERE token_symbol = %s AND source = %s
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """, (token_symbol, source))
                else:
                    cur.execute("""
                        SELECT snapshot_id, token_symbol, token_address, price_usd,
                               quote_token_symbol, quote_token_address, price_in_quote,
                               source, pair_address, reserve_token, reserve_quote, timestamp
                        FROM price_snapshots
                        WHERE token_symbol = %s
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """, (token_symbol,))
                
                row = cur.fetchone()
                if row:
                    return PriceSnapshot(
                        snapshot_id=row[0],
                        token_symbol=row[1],
                        token_address=row[2],
                        price_usd=row[3],
                        quote_token_symbol=row[4],
                        quote_token_address=row[5],
                        price_in_quote=row[6],
                        source=row[7],
                        pair_address=row[8],
                        reserve_token=row[9],
                        reserve_quote=row[10],
                        timestamp=row[11]
                    )
                return None
                
        except Exception as e:
            logger.error(f"Error getting latest price for {token_symbol}: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    # ============================================
    # Liqwid APY snapshot operations
    # ============================================
    
    def insert_liqwid_apy_snapshot(self, snapshot: LiqwidAPYSnapshot) -> int:
        """Insert a Liqwid APY snapshot and return its ID"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO liqwid_apy_snapshots (
                        asset_id, market_id, supply_apy, lq_supply_apy, total_supply_apy,
                        borrow_apy, total_supply, total_borrows, utilization_rate,
                        available_liquidity, total_supply_usd, total_borrows_usd,
                        token_price_usd, yield_type, timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING snapshot_id
                """, (
                    snapshot.asset_id,
                    snapshot.market_id,
                    snapshot.supply_apy,
                    snapshot.lq_supply_apy,
                    snapshot.total_supply_apy,
                    snapshot.borrow_apy,
                    snapshot.total_supply,
                    snapshot.total_borrows,
                    snapshot.utilization_rate,
                    snapshot.available_liquidity,
                    snapshot.total_supply_usd,
                    snapshot.total_borrows_usd,
                    snapshot.token_price_usd,
                    snapshot.yield_type or 'supply',
                    snapshot.timestamp or datetime.utcnow()
                ))
                
                snapshot_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Inserted Liqwid APY snapshot for asset {snapshot.asset_symbol} (id={snapshot_id})")
                return snapshot_id
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error inserting Liqwid APY snapshot: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    def get_latest_liqwid_apy(self, asset_symbol: str) -> Optional[LiqwidAPYSnapshot]:
        """Get the latest Liqwid APY snapshot for an asset"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT l.snapshot_id, l.asset_id, a.symbol, l.market_id,
                           l.supply_apy, l.lq_supply_apy, l.total_supply_apy, l.borrow_apy,
                           l.total_supply, l.total_borrows, l.utilization_rate,
                           l.available_liquidity, l.yield_type, l.timestamp
                    FROM liqwid_apy_snapshots l
                    JOIN assets a ON l.asset_id = a.asset_id
                    WHERE a.symbol = %s
                    ORDER BY l.timestamp DESC
                    LIMIT 1
                """, (asset_symbol,))
                
                row = cur.fetchone()
                if row:
                    return LiqwidAPYSnapshot(
                        snapshot_id=row[0],
                        asset_id=row[1],
                        asset_symbol=row[2],
                        market_id=row[3],
                        supply_apy=row[4],
                        lq_supply_apy=row[5],
                        total_supply_apy=row[6],
                        borrow_apy=row[7],
                        total_supply=row[8],
                        total_borrows=row[9],
                        utilization_rate=row[10],
                        available_liquidity=row[11],
                        yield_type=row[12],
                        timestamp=row[13]
                    )
                return None
                
        except Exception as e:
            logger.error(f"Error getting latest Liqwid APY for {asset_symbol}: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    def get_liqwid_apy_history(self, asset_symbol: str, days: int = 30) -> List[LiqwidAPYSnapshot]:
        """Get Liqwid APY history for an asset"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT l.snapshot_id, l.asset_id, a.symbol, l.market_id,
                           l.supply_apy, l.lq_supply_apy, l.total_supply_apy, l.borrow_apy,
                           l.total_supply, l.total_borrows, l.utilization_rate,
                           l.available_liquidity, l.yield_type, l.timestamp
                    FROM liqwid_apy_snapshots l
                    JOIN assets a ON l.asset_id = a.asset_id
                    WHERE a.symbol = %s
                      AND l.timestamp >= NOW() - INTERVAL '%s days'
                    ORDER BY l.timestamp DESC
                """, (asset_symbol, days))
                
                results = []
                for row in cur.fetchall():
                    results.append(LiqwidAPYSnapshot(
                        snapshot_id=row[0],
                        asset_id=row[1],
                        asset_symbol=row[2],
                        market_id=row[3],
                        supply_apy=row[4],
                        lq_supply_apy=row[5],
                        total_supply_apy=row[6],
                        borrow_apy=row[7],
                        total_supply=row[8],
                        total_borrows=row[9],
                        utilization_rate=row[10],
                        available_liquidity=row[11],
                        yield_type=row[12],
                        timestamp=row[13]
                    ))
                return results
                
        except Exception as e:
            logger.error(f"Error getting Liqwid APY history for {asset_symbol}: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    def get_all_latest_liqwid_apys(self) -> List[LiqwidAPYSnapshot]:
        """Get the latest Liqwid APY snapshot for all markets"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT ON (a.symbol)
                           l.snapshot_id, l.asset_id, a.symbol, l.market_id,
                           l.supply_apy, l.lq_supply_apy, l.total_supply_apy, l.borrow_apy,
                           l.total_supply, l.total_borrows, l.utilization_rate,
                           l.available_liquidity, l.yield_type, l.timestamp
                    FROM liqwid_apy_snapshots l
                    JOIN assets a ON l.asset_id = a.asset_id
                    ORDER BY a.symbol, l.timestamp DESC
                """)
                
                results = []
                for row in cur.fetchall():
                    results.append(LiqwidAPYSnapshot(
                        snapshot_id=row[0],
                        asset_id=row[1],
                        asset_symbol=row[2],
                        market_id=row[3],
                        supply_apy=row[4],
                        lq_supply_apy=row[5],
                        total_supply_apy=row[6],
                        borrow_apy=row[7],
                        total_supply=row[8],
                        total_borrows=row[9],
                        utilization_rate=row[10],
                        available_liquidity=row[11],
                        yield_type=row[12],
                        timestamp=row[13]
                    ))
                return results
                
        except Exception as e:
            logger.error(f"Error getting all latest Liqwid APYs: {e}")
            raise
        finally:
            self.db.return_connection(conn)
