#!/usr/bin/env python3
"""
Collection Status Check Script

This script checks if all protocols have collected data for today (EST).
Designed to run at 2 AM after the midnight and 1 AM backup runs complete.

Logs warnings for any protocols missing data, which can be used for alerting.

Usage:
    python scripts/check_collection_status.py

Cron example (2 AM daily):
    0 2 * * * cd /home/danladuke/DefiTracker && /home/danladuke/DefiTracker/venv/bin/python scripts/check_collection_status.py >> /var/log/defitracker/status.log 2>&1
"""

import sys
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import DatabaseConnection
from src.database.queries import DatabaseQueries, APYQueries

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Protocols to check (protocol_name, table_type)
# table_type: 'apr' for apr_snapshots, 'liqwid' for liqwid_apy_snapshots
PROTOCOLS_TO_CHECK = [
    ('minswap', 'apr'),
    ('sundaeswap', 'apr'),
    ('wingriders', 'apr'),
    ('liqwid', 'liqwid'),
]


def get_snapshot_count_for_date(db: DatabaseConnection, protocol_name: str,
                                 table_type: str, date_est) -> int:
    """Get the number of snapshots for a protocol on a given EST date."""
    est = ZoneInfo("America/New_York")
    from datetime import timedelta

    # Create datetime at start of day in EST, then convert to UTC
    start_of_day_est = datetime(date_est.year, date_est.month, date_est.day, tzinfo=est)
    end_of_day_est = start_of_day_est + timedelta(days=1)

    # Convert to UTC for database query
    start_utc = start_of_day_est.astimezone(ZoneInfo("UTC"))
    end_utc = end_of_day_est.astimezone(ZoneInfo("UTC"))

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            if table_type == 'apr':
                cur.execute(
                    """SELECT COUNT(*) FROM apr_snapshots s
                       JOIN protocols p ON s.protocol_id = p.protocol_id
                       WHERE p.name = %s
                         AND s.timestamp >= %s
                         AND s.timestamp < %s""",
                    (protocol_name, start_utc, end_utc)
                )
            elif table_type == 'liqwid':
                cur.execute(
                    """SELECT COUNT(*) FROM liqwid_apy_snapshots
                       WHERE timestamp >= %s
                         AND timestamp < %s""",
                    (start_utc, end_utc)
                )
            else:
                return 0

            result = cur.fetchone()
            return result[0] if result else 0
    finally:
        db.return_connection(conn)


def check_collection_status():
    """Check if all protocols have collected data for today."""
    est = ZoneInfo("America/New_York")
    today_est = datetime.now(est).date()

    logger.info("=" * 60)
    logger.info("Checking collection status for %s (EST)", today_est)
    logger.info("=" * 60)

    db = None
    try:
        db = DatabaseConnection()

        missing = []
        for protocol_name, table_type in PROTOCOLS_TO_CHECK:
            count = get_snapshot_count_for_date(db, protocol_name, table_type, today_est)

            if count > 0:
                logger.info("OK: %s has %d snapshots", protocol_name, count)
            else:
                logger.warning("WARNING: %s has 0 snapshots - COLLECTION FAILED", protocol_name)
                missing.append(protocol_name)

        logger.info("=" * 60)

        if missing:
            logger.error("ALERT: %d protocol(s) missing data: %s",
                        len(missing), ', '.join(missing))
            return 1
        else:
            logger.info("All protocols collected data successfully")
            return 0

    except Exception as e:
        logger.error("Status check failed: %s", e, exc_info=True)
        return 1
    finally:
        if db:
            try:
                db.close_all()
            except Exception:
                pass


def main():
    exit_code = check_collection_status()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
