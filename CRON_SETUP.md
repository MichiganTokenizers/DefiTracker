# Cron Setup for DefiTracker APY/APR Collection

## Overview

DefiTracker uses cron jobs to collect APY/APR data from multiple DeFi protocols across different blockchains. This guide covers setup for both development machines and Raspberry Pi servers.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Setup (All Collectors)](#quick-setup-all-collectors)
3. [Individual Collector Details](#individual-collector-details)
4. [Raspberry Pi Specific Setup](#raspberry-pi-specific-setup)
5. [Log Management](#log-management)
6. [Monitoring and Verification](#monitoring-and-verification)
7. [Troubleshooting](#troubleshooting)
8. [Future: Celery Upgrade](#future-celery-upgrade)

---

## Prerequisites

1. Database setup complete (PostgreSQL with tables created)
2. Python virtual environment with dependencies installed
3. Configuration file `config/chains.yaml` configured
4. All migrations applied to database

---

## Quick Setup (All Collectors)

### Step 1: Test Scripts First

Always test each script manually before scheduling:

```bash
cd ~/DefiTracker  # or /home/danladuke/Projects/DefiTracker
source venv/bin/activate

# Test each collector
python scripts/collect_kinetic_apy.py
python scripts/collect_liqwid_apy.py
python scripts/collect_minswap_apr.py
python scripts/collect_sundaeswap_apr.py
python scripts/collect_wingriders_apr.py
```

### Step 2: Create Logs Directory

```bash
mkdir -p ~/DefiTracker/logs
```

### Step 3: Add All Jobs to Crontab

Edit your crontab:
```bash
crontab -e
```

---

## Complete Crontab Configuration

### For Development Machine (Linux)

```cron
# ============================================
# DefiTracker APY/APR Collection Jobs
# Path: /home/danladuke/Projects/DefiTracker
# ============================================

# Kinetic APY (Flare blockchain) - daily at midnight UTC
0 0 * * * cd /home/danladuke/Projects/DefiTracker && /home/danladuke/Projects/DefiTracker/venv/bin/python scripts/collect_kinetic_apy.py >> logs/kinetic_collection.log 2>&1

# Liqwid APY (Cardano lending) - daily at 1:00 AM UTC
0 1 * * * cd /home/danladuke/Projects/DefiTracker && /home/danladuke/Projects/DefiTracker/venv/bin/python scripts/collect_liqwid_apy.py >> logs/liqwid_collection.log 2>&1

# SundaeSwap APR (Cardano DEX) - daily at 2:00 AM UTC
0 2 * * * cd /home/danladuke/Projects/DefiTracker && /home/danladuke/Projects/DefiTracker/venv/bin/python scripts/collect_sundaeswap_apr.py >> logs/sundaeswap_collection.log 2>&1

# WingRiders APR (Cardano DEX) - daily at 3:00 AM UTC
0 3 * * * cd /home/danladuke/Projects/DefiTracker && /home/danladuke/Projects/DefiTracker/venv/bin/python scripts/collect_wingriders_apr.py >> logs/wingriders_collection.log 2>&1

# Minswap APR (Cardano DEX) - daily at 10:00 AM UTC
0 10 * * * cd /home/danladuke/Projects/DefiTracker && /home/danladuke/Projects/DefiTracker/venv/bin/python scripts/collect_minswap_apr.py >> logs/minswap_collection.log 2>&1
```

### For Raspberry Pi Server

```cron
# ============================================
# DefiTracker APY/APR Collection Jobs
# Path: /home/pi/DefiTracker (Raspberry Pi)
# ============================================

# Kinetic APY (Flare blockchain) - daily at midnight UTC
0 0 * * * cd /home/pi/DefiTracker && /home/pi/DefiTracker/venv/bin/python scripts/collect_kinetic_apy.py >> logs/kinetic_collection.log 2>&1

# Liqwid APY (Cardano lending) - daily at 1:00 AM UTC
0 1 * * * cd /home/pi/DefiTracker && /home/pi/DefiTracker/venv/bin/python scripts/collect_liqwid_apy.py >> logs/liqwid_collection.log 2>&1

# SundaeSwap APR (Cardano DEX) - daily at 2:00 AM UTC
0 2 * * * cd /home/pi/DefiTracker && /home/pi/DefiTracker/venv/bin/python scripts/collect_sundaeswap_apr.py >> logs/sundaeswap_collection.log 2>&1

# WingRiders APR (Cardano DEX) - daily at 3:00 AM UTC
0 3 * * * cd /home/pi/DefiTracker && /home/pi/DefiTracker/venv/bin/python scripts/collect_wingriders_apr.py >> logs/wingriders_collection.log 2>&1

# Minswap APR (Cardano DEX) - daily at 10:00 AM UTC
0 10 * * * cd /home/pi/DefiTracker && /home/pi/DefiTracker/venv/bin/python scripts/collect_minswap_apr.py >> logs/minswap_collection.log 2>&1

# Weekly database backup - Sundays at 4:00 AM
0 4 * * 0 pg_dump -U postgres defi_apr_tracker | gzip > /mnt/ssd/backups/defi_backup_$(date +\%Y\%m\%d).sql.gz 2>&1
```

### Verify Cron Entry

```bash
crontab -l
```

---

## Individual Collector Details

### Kinetic APY (Flare)

**Script**: `scripts/collect_kinetic_apy.py`
**Table**: `kinetic_apy_snapshots`
**Data collected**:
- Supply APY (base + KFLR rewards)
- Borrow APY
- Market utilization
- TVL data

**Test command**:
```bash
cd ~/DefiTracker && source venv/bin/activate
python scripts/collect_kinetic_apy.py
```

---

### Liqwid APY (Cardano)

**Script**: `scripts/collect_liqwid_apy.py`
**Table**: `liqwid_apy_snapshots`
**Data collected**:
- Supply APY (base + LQ token rewards)
- Borrow APY
- Utilization rate
- Liquidity data

**Prerequisites**:
- Run migration `migrations/008_liqwid_apy_snapshots.sql`
- Enable `liqwid` in `config/chains.yaml` under `chains.cardano.protocols`

**Test command**:
```bash
cd ~/DefiTracker && source venv/bin/activate
python scripts/collect_liqwid_apy.py
```

---

### Minswap APR (Cardano)

**Script**: `scripts/collect_minswap_apr.py`
**Table**: `apr_snapshots`
**Data collected**:
- LP APR (farm rewards + trading fees)
- TVL in USD
- Pool version (v1/v2)

**Prerequisites**:
- Update `config/chains.yaml` with valid `farm_id` / `pool_id` for tracked pairs

**Test command**:
```bash
cd ~/DefiTracker && source venv/bin/activate
python scripts/collect_minswap_apr.py
```

---

### SundaeSwap APR (Cardano)

**Script**: `scripts/collect_sundaeswap_apr.py`
**Table**: `apr_snapshots`
**Data collected**:
- LP APR from yield farming
- TVL in USD
- Pool identifiers

**Test command**:
```bash
cd ~/DefiTracker && source venv/bin/activate
python scripts/collect_sundaeswap_apr.py
```

---

### WingRiders APR (Cardano)

**Script**: `scripts/collect_wingriders_apr.py`
**Table**: `apr_snapshots`
**Data collected**:
- LP APR from farms
- TVL in USD
- Farm rewards

**Test command**:
```bash
cd ~/DefiTracker && source venv/bin/activate
python scripts/collect_wingriders_apr.py
```

---

## Raspberry Pi Specific Setup

### Path Differences

| Environment | Project Path | Python Path |
|-------------|--------------|-------------|
| Development | `/home/danladuke/Projects/DefiTracker` | `/home/danladuke/Projects/DefiTracker/venv/bin/python` |
| Raspberry Pi | `/home/pi/DefiTracker` | `/home/pi/DefiTracker/venv/bin/python` |

### Staggered Schedule (Recommended for Pi)

To avoid overloading the Pi 400, collectors are scheduled at different times:

| Time (UTC) | Collector | Protocol | Chain |
|------------|-----------|----------|-------|
| 00:00 | collect_kinetic_apy.py | Kinetic | Flare |
| 01:00 | collect_liqwid_apy.py | Liqwid | Cardano |
| 02:00 | collect_sundaeswap_apr.py | SundaeSwap | Cardano |
| 03:00 | collect_wingriders_apr.py | WingRiders | Cardano |
| 10:00 | collect_minswap_apr.py | Minswap | Cardano |
| 04:00 (Sun) | Database backup | - | - |

### Full Raspberry Pi Setup

See [RASPBERRY_PI_SETUP.md](RASPBERRY_PI_SETUP.md) for complete setup instructions including:
- Hardware requirements and recommendations
- SSD setup for database storage
- PostgreSQL configuration
- systemd service for Flask web UI
- UPS configuration for safe shutdown

---

## Log Management

### Log File Locations

| Collector | Log File |
|-----------|----------|
| Kinetic | `logs/kinetic_collection.log` |
| Liqwid | `logs/liqwid_collection.log` |
| Minswap | `logs/minswap_collection.log` |
| SundaeSwap | `logs/sundaeswap_collection.log` |
| WingRiders | `logs/wingriders_collection.log` |

### View Recent Logs

```bash
# View last 100 lines
tail -100 logs/kinetic_collection.log

# View today's logs
grep "$(date +%Y-%m-%d)" logs/kinetic_collection.log

# Follow logs in real-time
tail -f logs/kinetic_collection.log
```

### Log Rotation (Recommended)

Create `/etc/logrotate.d/defitracker`:

```
/home/pi/DefiTracker/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 pi pi
}
```

For development machine, adjust path:
```
/home/danladuke/Projects/DefiTracker/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 danladuke danladuke
}
```

---

## Monitoring and Verification

### Check Last Run

```bash
# Last log entry for each collector
tail -1 logs/kinetic_collection.log
tail -1 logs/liqwid_collection.log
tail -1 logs/minswap_collection.log
tail -1 logs/sundaeswap_collection.log
tail -1 logs/wingriders_collection.log

# Last successful collection
grep "Collection complete" logs/kinetic_collection.log | tail -1
```

### Check Database

```sql
-- Latest Kinetic APY snapshots
SELECT a.symbol, k.total_supply_apy, k.borrow_apy, k.timestamp
FROM kinetic_apy_snapshots k
JOIN assets a ON k.asset_id = a.asset_id
ORDER BY k.timestamp DESC
LIMIT 10;

-- Latest Liqwid APY snapshots
SELECT a.symbol, l.supply_apy, l.lq_supply_apy, l.total_supply_apy, 
       l.borrow_apy, l.utilization_rate, l.timestamp
FROM liqwid_apy_snapshots l
JOIN assets a ON l.asset_id = a.asset_id
ORDER BY l.timestamp DESC
LIMIT 10;

-- Latest LP APR snapshots (Minswap, SundaeSwap, WingRiders)
SELECT p.name as protocol, a.symbol, s.apr, s.tvl_usd, s.timestamp
FROM apr_snapshots s
JOIN assets a ON s.asset_id = a.asset_id
JOIN protocols p ON s.protocol_id = p.protocol_id
ORDER BY s.timestamp DESC
LIMIT 20;

-- Count snapshots per day per protocol
SELECT 
    DATE(timestamp) as day, 
    p.name as protocol,
    COUNT(*) as snapshots
FROM apr_snapshots s
JOIN protocols p ON s.protocol_id = p.protocol_id
GROUP BY DATE(timestamp), p.name
ORDER BY day DESC, protocol
LIMIT 30;
```

### Quick Health Check

```bash
# Check cron service
systemctl status cron

# Check PostgreSQL
systemctl status postgresql

# Check DefiTracker web service (Raspberry Pi)
systemctl status defitracker

# Check all services at once
systemctl status cron postgresql defitracker
```

---

## Cron Schedule Options

| Schedule | Cron Expression | Description |
|----------|----------------|-------------|
| Daily midnight UTC | `0 0 * * *` | Standard daily collection |
| Every 6 hours | `0 */6 * * *` | More frequent snapshots |
| Every hour | `0 * * * *` | Highest granularity |
| Daily at 6 AM UTC | `0 6 * * *` | Adjust to preferred time |
| Every 12 hours | `0 0,12 * * *` | Twice daily |
| Weekly (Sundays) | `0 0 * * 0` | Weekly snapshots |

---

## Troubleshooting

### Script doesn't run

1. **Check cron is running**: 
   ```bash
   systemctl status cron
   ```

2. **Check cron logs**: 
   ```bash
   grep CRON /var/log/syslog | tail -20
   ```

3. **Test script manually first**:
   ```bash
   cd ~/DefiTracker && source venv/bin/activate
   python scripts/collect_kinetic_apy.py
   ```

4. **Check file permissions**:
   ```bash
   ls -la scripts/
   chmod +x scripts/*.py
   ```

### Database errors

1. **Check database is running**: 
   ```bash
   systemctl status postgresql
   ```

2. **Check connection**: 
   ```bash
   cat config/database.yaml
   ```

3. **Test connection**:
   ```bash
   psql -U postgres -d defi_apr_tracker -c "SELECT 1;"
   ```

4. **Ensure migrations have been run**:
   ```bash
   python src/database/setup.py
   ```

### Network errors

1. **Check Flare RPC is accessible**:
   ```bash
   curl -X POST https://flare-api.flare.network/ext/C/rpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
   ```

2. **Check Cardano APIs are reachable**:
   ```bash
   curl https://api.minswap.org/health
   ```

3. **Check DNS resolution**:
   ```bash
   nslookup api.minswap.org
   ```

### Raspberry Pi specific

1. **Check SSD is mounted**:
   ```bash
   df -h /mnt/ssd
   ```

2. **Check available memory**:
   ```bash
   free -h
   ```

3. **Check CPU temperature**:
   ```bash
   vcgencmd measure_temp
   ```

---

## Manual Collection

Run collection manually anytime:

```bash
cd ~/DefiTracker
source venv/bin/activate

# Run all collectors
python scripts/collect_kinetic_apy.py
python scripts/collect_liqwid_apy.py
python scripts/collect_minswap_apr.py
python scripts/collect_sundaeswap_apr.py
python scripts/collect_wingriders_apr.py
```

---

## Future: Celery Upgrade

When ready to upgrade to Celery for more robust task management:

### 1. Install Celery and Redis

```bash
pip install celery redis
```

### 2. Install and Start Redis

```bash
sudo apt install redis-server
sudo systemctl enable redis
sudo systemctl start redis
```

### 3. Benefits of Celery

- Retry logic for failed tasks
- Better error handling
- Distributed task execution
- Task monitoring dashboard (Flower)
- Priority queues

For now, cron is sufficient for daily collection and is simpler to maintain on a Raspberry Pi.

---

*Last updated: January 2026*
