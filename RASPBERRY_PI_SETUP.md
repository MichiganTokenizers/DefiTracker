# Raspberry Pi 400 DefiTracker Server Setup

Complete guide for setting up your Raspberry Pi 400 as an all-in-one DefiTracker server running PostgreSQL/TimescaleDB, Flask web UI, and scheduled cron jobs for APY/APR collection.

---

## Table of Contents

1. [Hardware Requirements](#hardware-requirements)
2. [Hardware Shopping List](#hardware-shopping-list)
3. [Phase 1: Prepare and Flash OS](#phase-1-prepare-and-flash-os)
4. [Phase 2: Initial Pi Configuration](#phase-2-initial-pi-configuration)
5. [Phase 3: Mount USB SSD for Database](#phase-3-mount-usb-ssd-for-database)
6. [Phase 4: Install PostgreSQL and TimescaleDB](#phase-4-install-postgresql-and-timescaledb)
7. [Phase 5: Deploy DefiTracker Project](#phase-5-deploy-defitracker-project)
8. [Phase 6: Configure Cron Jobs](#phase-6-configure-cron-jobs)
9. [Phase 7: Set Up Web UI as System Service](#phase-7-set-up-web-ui-as-system-service)
10. [Phase 8: UPS Safe Shutdown (Optional)](#phase-8-ups-safe-shutdown-optional)
11. [Maintenance and Monitoring](#maintenance-and-monitoring)
12. [Troubleshooting](#troubleshooting)

---

## Hardware Requirements

### Your Pi 400 Specs

| Component | Specification |
|-----------|---------------|
| CPU | Broadcom BCM2711 quad-core Cortex-A72 @ 1.8GHz |
| RAM | 4GB LPDDR4 |
| Storage | MicroSD slot + USB 3.0 ports |
| Form Factor | Keyboard-integrated (no standard HAT mounting) |

**4GB RAM is sufficient** for running PostgreSQL + Flask + cron jobs simultaneously. The Pi 400's improved thermal design (compared to Pi 4) helps with sustained workloads.

### X728-C1 Compatibility Notice

The X728-C1 UPS HAT is designed for standard Raspberry Pi boards and **will not work directly** with the Pi 400 because:
- Pi 400 has no exposed 40-pin GPIO header for HAT mounting
- Different physical form factor (keyboard chassis)

**Recommended alternatives** are listed below.

### Storage: Why You Need a USB SSD

**CRITICAL**: Do NOT run PostgreSQL on a MicroSD card for production use.

| Storage Type | Reliability | Write Speed | Database Suitability |
|--------------|-------------|-------------|---------------------|
| MicroSD | Low (wear-out after ~10K writes) | ~25 MB/s | Development only |
| **USB 3.0 SSD** | High (millions of writes) | ~400 MB/s | **Recommended** |
| USB HDD | Medium | ~100 MB/s | Acceptable |

PostgreSQL performs many small writes, which quickly degrades MicroSD cards.

### UPS Options for Pi 400

Since the X728-C1 won't fit, here are compatible alternatives:

| Option | Description | Pros | Cons | Price |
|--------|-------------|------|------|-------|
| **CyberPower CP425SLG** | Desktop UPS | Works with any device, proven reliability, 8-min runtime | Larger footprint | $50-70 |
| **APC BE425M** | Compact UPS | Small form factor, USB monitoring | Limited outlets | $50-60 |
| **UPSPack V3** | Inline USB-C battery | Very compact, connects inline | ~20 min runtime | $25-40 |
| **Anker PowerCore** | USB-C power bank | Portable, cheap | No low-battery signal | $20-30 |

**Recommendation**: A small desktop UPS (CyberPower or APC) provides the best protection for your database. It allows graceful shutdown on power loss via NUT (Network UPS Tools).

---

## Hardware Shopping List

| Item | Purpose | Where to Buy | Est. Cost |
|------|---------|--------------|-----------|
| USB 3.0 SSD 250-500GB | Database storage | Amazon, Best Buy | $40-70 |
| Samsung T7 500GB (recommended) | Fast, reliable, compact | Amazon | $55 |
| USB UPS (CyberPower CP425SLG) | Power protection | Amazon, Walmart | $50-70 |
| Ethernet cable (Cat6) | Reliable network | Amazon | $5-10 |
| **Total** | | | **$95-160** |

---

## Phase 1: Prepare and Flash OS

### Step 1.1: Download Raspberry Pi Imager

Visit https://www.raspberrypi.com/software/ and download the Imager for your current computer.

### Step 1.2: Prepare MicroSD Card

Insert a MicroSD card (32GB minimum, 64GB recommended) into your computer.

### Step 1.3: Flash Raspberry Pi OS

1. Open Raspberry Pi Imager
2. Click **Choose OS** → **Raspberry Pi OS (64-bit)** (full desktop version)
3. Click **Choose Storage** → Select your MicroSD card
4. Click the **gear icon** (⚙️) for advanced options:

**Configure these settings:**

```
☑ Set hostname: defitracker
☑ Enable SSH (Use password authentication)
☑ Set username and password:
    Username: pi
    Password: [your secure password]
☑ Configure wireless LAN:
    SSID: [your WiFi name]
    Password: [your WiFi password]
    Country: [your country code, e.g., US]
☑ Set locale settings:
    Time zone: [your timezone, e.g., America/New_York]
    Keyboard layout: us
```

5. Click **Save**, then **Write**
6. Wait for flashing to complete

### Step 1.4: First Boot

1. Insert the MicroSD card into your Pi 400
2. Connect to your monitor (HDMI)
3. Connect Ethernet cable (recommended) or use WiFi
4. Power on the Pi 400

---

## Phase 2: Initial Pi Configuration

### Step 2.1: Update the System

Open a terminal and run:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

### Step 2.2: Install Essential Tools

```bash
sudo apt install -y git curl wget vim htop
```

### Step 2.3: Set a Static IP Address (Recommended)

For reliable remote access, set a static IP:

**Option A: Using nmtui (graphical)**
```bash
sudo nmtui
```
Navigate to "Edit a connection" → Select your connection → Set IPv4 to Manual → Add your IP/Gateway/DNS.

**Option B: Edit dhcpcd.conf**
```bash
sudo nano /etc/dhcpcd.conf
```

Add at the end (adjust for your network):
```
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8
```

Apply changes:
```bash
sudo systemctl restart dhcpcd
```

### Step 2.4: Enable SSH (if not already)

```bash
sudo systemctl enable ssh
sudo systemctl start ssh
```

Now you can SSH from another computer:
```bash
ssh pi@192.168.1.100  # or your Pi's IP
```

---

## Phase 3: Mount USB SSD for Database

### Step 3.1: Connect and Identify the SSD

Plug in your USB SSD, then identify it:

```bash
lsblk
```

You should see something like:
```
sda           8:0    0 465.8G  0 disk 
└─sda1        8:1    0 465.8G  0 part 
```

### Step 3.2: Format the SSD (if new)

**WARNING**: This erases all data on the SSD!

```bash
# Create a new partition table and ext4 filesystem
sudo parted /dev/sda --script mklabel gpt
sudo parted /dev/sda --script mkpart primary ext4 0% 100%
sudo mkfs.ext4 /dev/sda1
```

### Step 3.3: Create Mount Point

```bash
sudo mkdir -p /mnt/ssd
```

### Step 3.4: Get the SSD's UUID

```bash
sudo blkid /dev/sda1
```

Output example:
```
/dev/sda1: UUID="a1b2c3d4-e5f6-7890-abcd-ef1234567890" TYPE="ext4"
```

### Step 3.5: Configure Auto-Mount on Boot

```bash
sudo nano /etc/fstab
```

Add this line (replace UUID with yours):
```
UUID=a1b2c3d4-e5f6-7890-abcd-ef1234567890 /mnt/ssd ext4 defaults,noatime 0 2
```

### Step 3.6: Mount and Verify

```bash
sudo mount -a
df -h /mnt/ssd
```

You should see your SSD mounted at `/mnt/ssd`.

### Step 3.7: Set Permissions

```bash
sudo chown -R postgres:postgres /mnt/ssd
```

---

## Phase 4: Install PostgreSQL and TimescaleDB

### Step 4.1: Install PostgreSQL

```bash
sudo apt install -y postgresql postgresql-contrib
```

### Step 4.2: Install TimescaleDB for ARM64

TimescaleDB has official ARM64 packages:

```bash
# Add TimescaleDB repository
sudo sh -c "echo 'deb https://packagecloud.io/timescale/timescaledb/debian/ $(lsb_release -c -s) main' > /etc/apt/sources.list.d/timescaledb.list"

# Add GPG key
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -

# Update and install
sudo apt update

# Get PostgreSQL version and install matching TimescaleDB
PG_VERSION=$(psql --version | grep -oP '\d+' | head -1)
sudo apt install -y timescaledb-2-postgresql-${PG_VERSION}
```

### Step 4.3: Configure TimescaleDB

```bash
sudo timescaledb-tune --quiet --yes
```

### Step 4.4: Move PostgreSQL Data to SSD

Stop PostgreSQL:
```bash
sudo systemctl stop postgresql
```

Move data directory to SSD:
```bash
sudo rsync -av /var/lib/postgresql/ /mnt/ssd/postgresql/
sudo mv /var/lib/postgresql /var/lib/postgresql.bak
sudo ln -s /mnt/ssd/postgresql /var/lib/postgresql
```

Fix permissions:
```bash
sudo chown -R postgres:postgres /mnt/ssd/postgresql
```

### Step 4.5: Start PostgreSQL

```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

Verify it's running:
```bash
sudo systemctl status postgresql
```

### Step 4.6: Create the Database

```bash
sudo -u postgres psql <<EOF
CREATE DATABASE defi_apr_tracker;
\c defi_apr_tracker
CREATE EXTENSION IF NOT EXISTS timescaledb;
\q
EOF
```

### Step 4.7: Set PostgreSQL Password

```bash
sudo -u postgres psql
```

In the PostgreSQL prompt:
```sql
ALTER USER postgres PASSWORD 'your_secure_password_here';
\q
```

### Step 4.8: Configure PostgreSQL for Network Access (Optional)

If you need to access the database from other machines:

```bash
sudo nano /etc/postgresql/*/main/postgresql.conf
```

Change:
```
listen_addresses = 'localhost'
```
to:
```
listen_addresses = '*'
```

Edit pg_hba.conf:
```bash
sudo nano /etc/postgresql/*/main/pg_hba.conf
```

Add (adjust network range):
```
host    all             all             192.168.1.0/24          md5
```

Restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

---

## Phase 5: Deploy DefiTracker Project

### Step 5.1: Clone or Copy the Project

**Option A: Clone from Git**
```bash
cd ~
git clone https://github.com/yourusername/DefiTracker.git
cd DefiTracker
```

**Option B: Copy from another machine via rsync**
```bash
# Run this from your development machine
rsync -avz --exclude='venv' --exclude='__pycache__' \
  ~/Projects/DefiTracker/ pi@192.168.1.100:~/DefiTracker/
```

### Step 5.2: Install Python Dependencies

```bash
# Install Python 3 and venv
sudo apt install -y python3 python3-venv python3-pip

# Create virtual environment
cd ~/DefiTracker
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5.3: Configure Database Connection

```bash
cp config/database.yaml.template config/database.yaml
nano config/database.yaml
```

Update with your settings:
```yaml
database:
  host: localhost
  port: 5432
  database: defi_apr_tracker
  user: postgres
  password: your_secure_password_here
```

### Step 5.4: Run Database Setup

```bash
source venv/bin/activate
python src/database/setup.py
```

This will:
- Create all database tables
- Set up TimescaleDB hypertables
- Initialize blockchains and protocols from `config/chains.yaml`

### Step 5.5: Verify Setup

```bash
# Test database connection
python -c "from src.database.connection import DatabaseConnection; db = DatabaseConnection(); conn = db.get_connection(); print('Database connected!'); db.return_connection(conn)"

# Check tables
sudo -u postgres psql -d defi_apr_tracker -c "\dt"
```

### Step 5.6: Test Collection Scripts

```bash
source venv/bin/activate

# Test Kinetic collection
python scripts/collect_kinetic_apy.py

# Test Minswap collection
python scripts/collect_minswap_apr.py
```

### Step 5.7: Create Log Directory

```bash
mkdir -p ~/DefiTracker/logs
```

---

## Phase 6: Configure Cron Jobs

### Step 6.1: Edit Crontab

```bash
crontab -e
```

### Step 6.2: Add All Collection Jobs

Add these lines (adjust paths if you installed elsewhere):

```cron
# DefiTracker APY/APR Collection Jobs
# ====================================

# Kinetic APY (Flare) - daily at midnight UTC
0 0 * * * cd /home/pi/DefiTracker && /home/pi/DefiTracker/venv/bin/python scripts/collect_kinetic_apy.py >> logs/kinetic_collection.log 2>&1

# Liqwid APY (Cardano) - daily at 1:00 AM UTC
0 1 * * * cd /home/pi/DefiTracker && /home/pi/DefiTracker/venv/bin/python scripts/collect_liqwid_apy.py >> logs/liqwid_collection.log 2>&1

# SundaeSwap APR (Cardano) - daily at 2:00 AM UTC
0 2 * * * cd /home/pi/DefiTracker && /home/pi/DefiTracker/venv/bin/python scripts/collect_sundaeswap_apr.py >> logs/sundaeswap_collection.log 2>&1

# WingRiders APR (Cardano) - daily at 3:00 AM UTC
0 3 * * * cd /home/pi/DefiTracker && /home/pi/DefiTracker/venv/bin/python scripts/collect_wingriders_apr.py >> logs/wingriders_collection.log 2>&1

# Minswap APR (Cardano) - daily at 10:00 AM UTC
0 10 * * * cd /home/pi/DefiTracker && /home/pi/DefiTracker/venv/bin/python scripts/collect_minswap_apr.py >> logs/minswap_collection.log 2>&1
```

### Step 6.3: Verify Cron Jobs

```bash
crontab -l
```

### Step 6.4: Check Cron Service

```bash
sudo systemctl status cron
```

---

## Phase 7: Set Up Web UI as System Service

### Step 7.1: Create systemd Service File

```bash
sudo nano /etc/systemd/system/defitracker.service
```

Add this content:

```ini
[Unit]
Description=DefiTracker Web UI
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/DefiTracker
Environment="PATH=/home/pi/DefiTracker/venv/bin"
Environment="FLASK_APP=src.api.app:app"
ExecStart=/home/pi/DefiTracker/venv/bin/python -m flask run --host=0.0.0.0 --port=5000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Step 7.2: Enable and Start the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable defitracker
sudo systemctl start defitracker
```

### Step 7.3: Check Service Status

```bash
sudo systemctl status defitracker
```

### Step 7.4: View Logs

```bash
sudo journalctl -u defitracker -f
```

### Step 7.5: Access the Web UI

Open a browser and navigate to:
```
http://192.168.1.100:5000
```
(Replace with your Pi's IP address)

---

## Phase 8: UPS Safe Shutdown (Optional)

If using a UPS with USB connection (like CyberPower), you can configure automatic safe shutdown.

### Step 8.1: Install NUT (Network UPS Tools)

```bash
sudo apt install -y nut nut-client
```

### Step 8.2: Identify Your UPS

Connect UPS via USB, then:
```bash
sudo nut-scanner -U
```

### Step 8.3: Configure UPS

```bash
sudo nano /etc/nut/ups.conf
```

Add (adjust driver based on your UPS):
```ini
[myups]
    driver = usbhid-ups
    port = auto
    desc = "CyberPower UPS"
```

### Step 8.4: Configure UPS Monitor

```bash
sudo nano /etc/nut/upsmon.conf
```

Add:
```ini
MONITOR myups@localhost 1 admin password master
SHUTDOWNCMD "/sbin/shutdown -h now"
```

### Step 8.5: Set NUT Mode

```bash
sudo nano /etc/nut/nut.conf
```

Set:
```ini
MODE=standalone
```

### Step 8.6: Start NUT Services

```bash
sudo systemctl enable nut-server nut-client
sudo systemctl start nut-server nut-client
```

### Step 8.7: Test UPS Status

```bash
upsc myups
```

---

## Maintenance and Monitoring

### Check All Services

```bash
# PostgreSQL
sudo systemctl status postgresql

# DefiTracker Web UI
sudo systemctl status defitracker

# Cron
sudo systemctl status cron
```

### View Collection Logs

```bash
# Recent Kinetic collection
tail -50 ~/DefiTracker/logs/kinetic_collection.log

# All logs
ls -la ~/DefiTracker/logs/
```

### Database Size

```bash
sudo -u postgres psql -d defi_apr_tracker -c "
SELECT pg_size_pretty(pg_database_size('defi_apr_tracker'));
"
```

### SSD Health

```bash
# Check disk usage
df -h /mnt/ssd

# Check for errors
sudo dmesg | grep -i error
```

### System Resources

```bash
htop
```

### Database Backup (Weekly Recommended)

Add to crontab for weekly backups:
```cron
# Weekly database backup - Sundays at 4 AM
0 4 * * 0 pg_dump -U postgres defi_apr_tracker | gzip > /mnt/ssd/backups/defi_backup_$(date +\%Y\%m\%d).sql.gz
```

Create backup directory:
```bash
sudo mkdir -p /mnt/ssd/backups
sudo chown pi:pi /mnt/ssd/backups
```

---

## Troubleshooting

### PostgreSQL Won't Start

```bash
# Check logs
sudo journalctl -u postgresql

# Check if data directory exists
ls -la /mnt/ssd/postgresql/

# Check permissions
sudo chown -R postgres:postgres /mnt/ssd/postgresql
```

### Web UI Not Accessible

```bash
# Check service status
sudo systemctl status defitracker

# Check if port is listening
sudo netstat -tlnp | grep 5000

# Check firewall (if enabled)
sudo ufw status
sudo ufw allow 5000
```

### Cron Jobs Not Running

```bash
# Check cron logs
grep CRON /var/log/syslog | tail -20

# Test script manually
cd ~/DefiTracker && source venv/bin/activate && python scripts/collect_kinetic_apy.py
```

### Network Issues

```bash
# Check connectivity
ping -c 4 google.com

# Check DNS
nslookup api.flare.network

# Restart networking
sudo systemctl restart NetworkManager
```

### SSD Not Mounting

```bash
# Check if SSD is detected
lsblk

# Check fstab syntax
sudo mount -a

# Manual mount
sudo mount /dev/sda1 /mnt/ssd
```

---

## Quick Reference

| Service | Command |
|---------|---------|
| Start Web UI | `sudo systemctl start defitracker` |
| Stop Web UI | `sudo systemctl stop defitracker` |
| Restart Web UI | `sudo systemctl restart defitracker` |
| View Web UI logs | `sudo journalctl -u defitracker -f` |
| Start PostgreSQL | `sudo systemctl start postgresql` |
| Check cron jobs | `crontab -l` |
| Manual collection | `cd ~/DefiTracker && source venv/bin/activate && python scripts/collect_kinetic_apy.py` |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Raspberry Pi 400                         │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Flask     │  │    Cron     │  │    PostgreSQL       │ │
│  │  Web UI     │  │  Scheduler  │  │    TimescaleDB      │ │
│  │  :5000      │  │  (daily)    │  │                     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         │                │                     │            │
│         └────────────────┼─────────────────────┘            │
│                          │                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │       USB 3.0 SSD       │
              │   (Database Storage)    │
              └─────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │         UPS             │
              │   (Power Protection)    │
              └─────────────────────────┘
                           │
                      [Mains Power]
```

---

*Last updated: January 2026*

