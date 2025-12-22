# Cron Setup for Kinetic APY Collection

## Overview

The collection script `scripts/collect_kinetic_apy.py` collects APY data from Kinetic protocol and stores it in the database. It's designed to run daily via cron.

## Prerequisites

1. Database setup complete (PostgreSQL with tables created)
2. Python virtual environment with dependencies installed
3. Configuration file `config/chains.yaml` configured

## Quick Setup

### 1. Test the Script First

```bash
cd /home/danladuke/Projects/DefiTracker
source venv/bin/activate
python scripts/collect_kinetic_apy.py
```

### 2. Add to Crontab

Edit your crontab:
```bash
crontab -e
```

Add this line for daily collection at midnight UTC:
```cron
0 0 * * * cd /home/danladuke/Projects/DefiTracker && /home/danladuke/Projects/DefiTracker/venv/bin/python scripts/collect_kinetic_apy.py >> logs/kinetic_collection.log 2>&1
```

### 3. Verify Cron Entry

```bash
crontab -l
```

## Cron Schedule Options

| Schedule | Cron Expression | Description |
|----------|----------------|-------------|
| Daily midnight UTC | `0 0 * * *` | Recommended for starting |
| Every 6 hours | `0 */6 * * *` | More frequent snapshots |
| Every hour | `0 * * * *` | Highest granularity |
| Daily at 6 AM UTC | `0 6 * * *` | Adjust to preferred time |

## Log Files

Logs are stored in `logs/kinetic_collection.log`

View recent logs:
```bash
tail -100 logs/kinetic_collection.log
```

View today's logs:
```bash
grep "$(date +%Y-%m-%d)" logs/kinetic_collection.log
```

## Log Rotation (Optional)

Create `/etc/logrotate.d/kinetic-collection`:
```
/home/danladuke/Projects/DefiTracker/logs/kinetic_collection.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
}
```

## Monitoring

### Check Last Run

```bash
# Last log entry
tail -1 logs/kinetic_collection.log

# Last successful collection
grep "Collection complete" logs/kinetic_collection.log | tail -1
```

### Check Database

```sql
-- Latest APY snapshots
SELECT a.symbol, k.total_supply_apy, k.borrow_apy, k.timestamp
FROM kinetic_apy_snapshots k
JOIN assets a ON k.asset_id = a.asset_id
ORDER BY k.timestamp DESC
LIMIT 10;

-- Count snapshots per day
SELECT DATE(timestamp) as day, COUNT(*) as snapshots
FROM kinetic_apy_snapshots
GROUP BY DATE(timestamp)
ORDER BY day DESC
LIMIT 7;
```

## Troubleshooting

### Script doesn't run

1. Check cron is running: `systemctl status cron`
2. Check cron logs: `grep CRON /var/log/syslog`
3. Test script manually first

### Database errors

1. Check database is running: `systemctl status postgresql`
2. Check connection in `config/database.yaml`
3. Ensure migrations have been run

### Network errors

1. Check Flare RPC is accessible
2. Check BlazeSwap contracts are reachable
3. Consider adding retry logic if needed

## Manual Collection

Run collection manually anytime:
```bash
cd /home/danladuke/Projects/DefiTracker
source venv/bin/activate
python scripts/collect_kinetic_apy.py
```

---

# Cron Setup for Minswap APR Collection

## Overview

The script `scripts/collect_minswap_apr.py` pulls APR data for configured Minswap pools (e.g., NIGHT-ADA) and stores them in `apr_snapshots`.

### Prerequisites

1. Update `config/chains.yaml` with valid `farm_id` / `pool_id` for the pairs you want to track.
2. Database and virtualenv set up as above.

### Test the Script

```bash
cd /home/danladuke/Projects/DefiTracker
source venv/bin/activate
python scripts/collect_minswap_apr.py
```

### Add to Crontab (daily 10:00 AM server time)

```cron
0 10 * * * cd /home/danladuke/Projects/DefiTracker && /home/danladuke/Projects/DefiTracker/venv/bin/python scripts/collect_minswap_apr.py >> logs/minswap_collection.log 2>&1
```

### Logs

- Kinetic: `logs/kinetic_collection.log`
- Minswap: `logs/minswap_collection.log`

## Upgrading to Celery (Future)

When ready to upgrade to Celery for more robust task management:

1. Install Celery and Redis:
   ```bash
   pip install celery redis
   ```

2. Start Redis:
   ```bash
   sudo apt install redis-server
   sudo systemctl start redis
   ```

3. Create Celery configuration (see future documentation)

For now, cron is sufficient for daily collection.

