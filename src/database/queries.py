"""Database query functions for APR tracking"""
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from psycopg2.extras import RealDictCursor
from src.database.connection import DatabaseConnection
from src.database.models import APRSnapshot
import logging

logger = logging.getLogger(__name__)


class DatabaseQueries:
    """Database query operations"""
    
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
                # Try to get existing
                cur.execute(
                    "SELECT blockchain_id FROM blockchains WHERE name = %s",
                    (name,)
                )
                result = cur.fetchone()
                
                if result:
                    return result[0]
                
                # Create new
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
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
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
                # Try to get existing
                cur.execute(
                    """SELECT protocol_id FROM protocols 
                       WHERE blockchain_id = %s AND name = %s""",
                    (blockchain_id, name)
                )
                result = cur.fetchone()
                
                if result:
                    return result[0]
                
                # Create new
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
    # Asset Operations
    # ============================================
    
    def get_or_create_asset(self, symbol: str, name: Optional[str] = None, 
                           contract_address: Optional[str] = None, 
                           decimals: int = 18) -> int:
        """Get asset ID, create if doesn't exist"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                # Try to get existing (match by symbol and contract_address)
                cur.execute(
                    """SELECT asset_id FROM assets 
                       WHERE symbol = %s AND 
                       (contract_address = %s OR (contract_address IS NULL AND %s IS NULL))""",
                    (symbol, contract_address, contract_address)
                )
                result = cur.fetchone()
                
                if result:
                    return result[0]
                
                # Create new
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
    
    def get_asset_id(self, symbol: str, contract_address: Optional[str] = None) -> Optional[int]:
        """Get asset ID by symbol and optional contract address"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT asset_id FROM assets 
                       WHERE symbol = %s AND 
                       (contract_address = %s OR (contract_address IS NULL AND %s IS NULL))""",
                    (symbol, contract_address, contract_address)
                )
                result = cur.fetchone()
                return result[0] if result else None
        finally:
            self.db.return_connection(conn)
    
    # ============================================
    # APR Snapshot Operations
    # ============================================
    
    def insert_apr_snapshot(self, blockchain_id: int, protocol_id: int, 
                           asset_id: int, apr: Decimal, 
                           timestamp: Optional[datetime] = None) -> int:
        """Insert a new APR snapshot"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO apr_snapshots 
                       (blockchain_id, protocol_id, asset_id, apr, timestamp)
                       VALUES (%s, %s, %s, %s, %s)
                       RETURNING snapshot_id""",
                    (blockchain_id, protocol_id, asset_id, apr, timestamp)
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
    
    def insert_bulk_apr_snapshots(self, snapshots: List[Tuple[int, int, int, Decimal, datetime]]) -> int:
        """Insert multiple APR snapshots efficiently"""
        if not snapshots:
            return 0
        
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO apr_snapshots 
                       (blockchain_id, protocol_id, asset_id, apr, timestamp)
                       VALUES (%s, %s, %s, %s, %s)""",
                    snapshots
                )
                count = cur.rowcount
                conn.commit()
                logger.info(f"Inserted {count} APR snapshots")
                return count
        except Exception as e:
            conn.rollback()
            logger.error(f"Error inserting bulk APR snapshots: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    def get_latest_aprs(self, blockchain_name: Optional[str] = None,
                       protocol_name: Optional[str] = None,
                       asset_symbol: Optional[str] = None) -> List[Dict]:
        """Get latest APR values with optional filters"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
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
    
    def get_historical_aprs(self, blockchain_name: str, protocol_name: str,
                           asset_symbol: str, days: int = 30) -> List[Dict]:
        """Get historical APR data for a specific asset"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """SELECT 
                        s.timestamp,
                        s.apr,
                        b.name AS blockchain,
                        p.name AS protocol,
                        a.symbol AS asset
                       FROM apr_snapshots s
                       JOIN blockchains b ON s.blockchain_id = b.blockchain_id
                       JOIN protocols p ON s.protocol_id = p.protocol_id
                       JOIN assets a ON s.asset_id = a.asset_id
                       WHERE b.name = %s
                         AND p.name = %s
                         AND a.symbol = %s
                         AND s.timestamp >= %s
                       ORDER BY s.timestamp DESC""",
                    (blockchain_name, protocol_name, asset_symbol, 
                     datetime.utcnow() - timedelta(days=days))
                )
                return [dict(row) for row in cur.fetchall()]
        finally:
            self.db.return_connection(conn)
    
    def get_apr_statistics(self, blockchain_name: str, protocol_name: str,
                          asset_symbol: str, days: int = 7) -> Dict:
        """Get APR statistics (avg, min, max) over time period"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if TimescaleDB is available
                cur.execute(
                    """SELECT 
                        AVG(s.apr) AS avg_apr,
                        MIN(s.apr) AS min_apr,
                        MAX(s.apr) AS max_apr,
                        COUNT(*) AS data_points
                       FROM apr_snapshots s
                       JOIN blockchains b ON s.blockchain_id = b.blockchain_id
                       JOIN protocols p ON s.protocol_id = p.protocol_id
                       JOIN assets a ON s.asset_id = a.asset_id
                       WHERE b.name = %s
                         AND p.name = %s
                         AND a.symbol = %s
                         AND s.timestamp >= %s""",
                    (blockchain_name, protocol_name, asset_symbol,
                     datetime.utcnow() - timedelta(days=days))
                )
                result = cur.fetchone()
                if result:
                    return dict(result)
                return {}
        finally:
            self.db.return_connection(conn)
    
    # ============================================
    # Collection Log Operations
    # ============================================
    
    def start_collection_log(self) -> int:
        """Start a new collection log entry"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO collection_logs (status, started_at)
                       VALUES ('running', CURRENT_TIMESTAMP)
                       RETURNING log_id""",
                )
                log_id = cur.fetchone()[0]
                conn.commit()
                return log_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Error starting collection log: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    def complete_collection_log(self, log_id: int, status: str, 
                                chains_collected: int, snapshots_created: int,
                                error_message: Optional[str] = None):
        """Complete a collection log entry"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE collection_logs 
                       SET status = %s,
                           completed_at = CURRENT_TIMESTAMP,
                           chains_collected = %s,
                           snapshots_created = %s,
                           error_message = %s
                       WHERE log_id = %s""",
                    (status, chains_collected, snapshots_created, error_message, log_id)
                )
                conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error completing collection log: {e}")
            raise
        finally:
            self.db.return_connection(conn)

