"""Database setup and initialization"""
import psycopg2
from psycopg2 import sql
from pathlib import Path
import yaml
import logging
from src.database.connection import DatabaseConnection
from src.database.queries import DatabaseQueries

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration_file(conn, migration_file: Path):
    """Run a SQL migration file"""
    logger.info(f"Running migration: {migration_file.name}")
    
    with open(migration_file, 'r') as f:
        sql_content = f.read()
    
    # Split by semicolons and execute each statement
    # Skip comments and empty statements
    statements = [
        stmt.strip() 
        for stmt in sql_content.split(';') 
        if stmt.strip() and not stmt.strip().startswith('--')
    ]
    
    with conn.cursor() as cur:
        for statement in statements:
            if statement:
                try:
                    cur.execute(statement)
                except Exception as e:
                    # Some statements might fail if already executed (like CREATE EXTENSION)
                    if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                        logger.warning(f"Statement already executed (skipping): {e}")
                    else:
                        raise
        conn.commit()
    logger.info(f"Migration {migration_file.name} completed")


def setup_database(create_timescaledb: bool = True):
    """Set up the database schema"""
    db = DatabaseConnection()
    conn = db.get_connection()
    
    try:
        migrations_dir = Path(__file__).parent.parent.parent / "migrations"
        
        # Run initial schema
        migration_001 = migrations_dir / "001_initial_schema.sql"
        if migration_001.exists():
            run_migration_file(conn, migration_001)
        else:
            logger.warning(f"Migration file not found: {migration_001}")
        
        # Run TimescaleDB setup (optional, requires superuser)
        if create_timescaledb:
            migration_002 = migrations_dir / "002_setup_timescaledb.sql"
            if migration_002.exists():
                try:
                    run_migration_file(conn, migration_002)
                except Exception as e:
                    logger.warning(f"TimescaleDB setup failed (may need superuser): {e}")
                    logger.info("Continuing without TimescaleDB hypertable...")
            else:
                logger.warning(f"TimescaleDB migration file not found: {migration_002}")
        
        logger.info("Database setup completed successfully")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Database setup failed: {e}")
        raise
    finally:
        db.return_connection(conn)


def initialize_from_config():
    """Initialize blockchains and protocols from chains.yaml config"""
    from src.collectors.chain_registry import ChainRegistry
    
    logger.info("Initializing blockchains and protocols from config...")
    
    registry = ChainRegistry()
    queries = DatabaseQueries()
    
    # Load chain configs
    config_path = Path(__file__).parent.parent.parent / "config" / "chains.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    chains_config = config.get('chains', {})
    
    for chain_name, chain_config in chains_config.items():
        if not chain_config.get('enabled', False):
            continue
        
        # Create blockchain
        blockchain_id = queries.get_or_create_blockchain(
            name=chain_name,
            chain_id=chain_config.get('chain_id'),
            rpc_url=chain_config.get('rpc_url')
        )
        
        # Create protocols
        protocols_config = chain_config.get('protocols', {})
        for protocol_name, protocol_config in protocols_config.items():
            if not protocol_config.get('enabled', False):
                continue
            
            queries.get_or_create_protocol(
                blockchain_id=blockchain_id,
                name=protocol_name,
                api_url=protocol_config.get('api_url')
            )
        
        logger.info(f"Initialized chain: {chain_name} with {len(protocols_config)} protocols")


def verify_setup():
    """Verify database setup is correct"""
    logger.info("Verifying database setup...")
    
    queries = DatabaseQueries()
    
    # Check tables exist
    db = DatabaseConnection()
    conn = db.get_connection()
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('blockchains', 'protocols', 'assets', 'apr_snapshots')
                ORDER BY table_name
            """)
            tables = [row[0] for row in cur.fetchall()]
            
            expected_tables = ['apr_snapshots', 'assets', 'blockchains', 'protocols']
            missing = set(expected_tables) - set(tables)
            
            if missing:
                logger.error(f"Missing tables: {missing}")
                return False
            
            logger.info(f"All required tables exist: {tables}")
            
            # Check TimescaleDB hypertable (if TimescaleDB is installed)
            try:
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM timescaledb_information.hypertables 
                    WHERE hypertable_name = 'apr_snapshots'
                """)
                is_hypertable = cur.fetchone()[0] > 0
                
                if is_hypertable:
                    logger.info("apr_snapshots is configured as TimescaleDB hypertable")
                else:
                    logger.warning("apr_snapshots is NOT a TimescaleDB hypertable (may need superuser)")
            except Exception as e:
                # TimescaleDB not installed or not accessible
                logger.info("TimescaleDB not installed - using standard PostgreSQL tables (this is fine)")
            
            return True
            
    finally:
        db.return_connection(conn)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--no-timescaledb':
        setup_database(create_timescaledb=False)
    else:
        setup_database(create_timescaledb=True)
    
    initialize_from_config()
    verify_setup()

