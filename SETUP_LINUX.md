# Linux Setup Guide for DefiTracker

## Quick Setup Steps

### 1. Install PostgreSQL and TimescaleDB

Run the automated setup script (requires sudo):

```bash
cd ~/Projects/DefiTracker
sudo bash setup_postgres.sh
```

**OR** install manually:

```bash
# Install PostgreSQL
sudo apt update
sudo apt install -y postgresql postgresql-contrib

# Install TimescaleDB repository
sudo sh -c "echo 'deb https://packagecloud.io/timescale/timescaledb/debian/ $(lsb_release -c -s) main' > /etc/apt/sources.list.d/timescaledb.list"
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -
sudo apt-get update

# Get PostgreSQL version
PG_VERSION=$(psql --version | grep -oP '\d+' | head -1)
sudo apt-get install -y timescaledb-2-postgresql-${PG_VERSION}

# Configure TimescaleDB
sudo timescaledb-tune --quiet --yes

# Start PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

### 2. Create Database

```bash
# Switch to postgres user and create database
sudo -u postgres psql <<EOF
CREATE DATABASE defi_apr_tracker;
\c defi_apr_tracker
CREATE EXTENSION IF NOT EXISTS timescaledb;
\q
EOF
```

### 3. Set PostgreSQL Password (if needed)

If you need to set a password for the postgres user:

```bash
sudo -u postgres psql
ALTER USER postgres PASSWORD 'your_password_here';
\q
```

### 4. Create Database Configuration

```bash
cd ~/Projects/DefiTracker
cp config/database.yaml.template config/database.yaml
nano config/database.yaml  # or use your preferred editor
```

Update the password in `config/database.yaml`:
```yaml
database:
  host: localhost
  port: 5432
  database: defi_apr_tracker
  user: postgres
  password: your_actual_password_here
```

### 5. Activate Virtual Environment and Run Setup

```bash
cd ~/Projects/DefiTracker
source venv/bin/activate
python src/database/setup.py
```

This will:
- Create all database tables
- Set up TimescaleDB hypertable (if you have permissions)
- Initialize blockchains and protocols from `config/chains.yaml`

### 6. Verify Setup

```bash
# Test database connection
python -c "from src.database.connection import DatabaseConnection; db = DatabaseConnection(); conn = db.get_connection(); print('Connected!'); db.return_connection(conn)"

# Check tables
sudo -u postgres psql -d defi_apr_tracker -c "\dt"
```

## Troubleshooting

### PostgreSQL not starting
```bash
sudo systemctl status postgresql
sudo journalctl -u postgresql
```

### Permission denied errors
- Make sure you're using the `postgres` user or have proper permissions
- Check `pg_hba.conf` if authentication fails

### TimescaleDB extension fails
- Run setup with `--no-timescaledb` flag: `python src/database/setup.py --no-timescaledb`
- The system works fine without TimescaleDB, it's just an optimization

### Connection refused
- Check PostgreSQL is running: `sudo systemctl status postgresql`
- Check it's listening: `sudo netstat -tlnp | grep 5432`

