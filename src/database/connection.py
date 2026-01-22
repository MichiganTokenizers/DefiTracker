"""Database connection management"""
import psycopg
from psycopg_pool import ConnectionPool
from typing import Optional
import yaml
from pathlib import Path


class DatabaseConnection:
    """Manages database connection pool"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "database.yaml"
        self.config_path = Path(config_path)
        self.connection_pool: Optional[ConnectionPool] = None
        self.load_config()

    def load_config(self):
        """Load database configuration"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Database config not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)

        self.db_config = config.get('database', {})

    def get_connection_pool(self):
        """Get or create connection pool"""
        if self.connection_pool is None:
            conninfo = (
                f"host={self.db_config.get('host', 'localhost')} "
                f"port={self.db_config.get('port', 5432)} "
                f"dbname={self.db_config.get('database')} "
                f"user={self.db_config.get('user')} "
                f"password={self.db_config.get('password')}"
            )
            self.connection_pool = ConnectionPool(conninfo, min_size=1, max_size=10)
        return self.connection_pool

    def get_connection(self):
        """Get a connection from the pool"""
        pool = self.get_connection_pool()
        return pool.getconn()

    def return_connection(self, conn):
        """Return a connection to the pool"""
        pool = self.get_connection_pool()
        pool.putconn(conn)

    def close_all(self):
        """Close all connections in the pool"""
        if self.connection_pool:
            self.connection_pool.close()
            self.connection_pool = None
