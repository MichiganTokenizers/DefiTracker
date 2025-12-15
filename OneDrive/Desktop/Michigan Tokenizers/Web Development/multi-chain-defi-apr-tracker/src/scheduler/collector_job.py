"""Scheduled job for collecting APR data"""
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from src.collectors.chain_registry import ChainRegistry
from src.database.connection import DatabaseConnection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def collect_apr_data():
    """Collect APR data from all active chains"""
    logger.info("Starting APR data collection")
    
    registry = ChainRegistry()
    db = DatabaseConnection()
    
    try:
        aprs = registry.collect_all_aprs()
        
        # TODO: Store APR data in database
        # For now, just log the results
        logger.info(f"Collected APR data: {aprs}")
        
    except Exception as e:
        logger.error(f"Error collecting APR data: {e}", exc_info=True)
    finally:
        db.close_all()


def start_scheduler():
    """Start the scheduler for daily APR collection"""
    scheduler = BlockingScheduler()
    
    # Schedule daily collection at midnight UTC
    scheduler.add_job(
        collect_apr_data,
        trigger=CronTrigger(hour=0, minute=0),
        id='daily_apr_collection',
        name='Daily APR Data Collection',
        replace_existing=True
    )
    
    logger.info("Scheduler started. Daily collection scheduled for midnight UTC.")
    scheduler.start()


if __name__ == '__main__':
    start_scheduler()
