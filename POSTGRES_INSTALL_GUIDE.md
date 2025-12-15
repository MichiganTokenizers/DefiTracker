# PostgreSQL Installation Guide for DefiTracker

## Step-by-Step Installation

### Step 1: Install PostgreSQL

Run these commands in your terminal:

```bash
# Update package list
sudo apt-get update

# Install PostgreSQL and contrib packages
sudo apt-get install -y postgresql postgresql-contrib

# Verify installation
psql --version
```

### Step 2: Start PostgreSQL Service

```bash
# Start PostgreSQL service
sudo systemctl start postgresql

# Enable PostgreSQL to start on boot
sudo systemctl enable postgresql

# Check service status
sudo systemctl status postgresql
```

### Step 3: Set PostgreSQL Password (if needed)

If you need to set or change the postgres user password:

```bash
# Switch to postgres user
sudo -u postgres psql

# In psql prompt, set password:
ALTER USER postgres PASSWORD 'your_secure_password_here';
\q
```

**Remember this password** - you'll need it for the database configuration!

### Step 4: Create Database and Enable TimescaleDB (Optional)

**Option A: With TimescaleDB (Recommended for time-series optimization)**

First, install TimescaleDB:

```bash
# Add TimescaleDB repository
sudo sh -c "echo 'deb https://packagecloud.io/timescale/timescaledb/debian/ $(lsb_release -c -s) main' > /etc/apt/sources.list.d/timescaledb.list"

# Add GPG key
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -

# Update and install
sudo apt-get update
sudo apt-get install -y timescaledb-2-postgresql-$(psql --version | grep -oP '\d+' | head -1)

# Configure TimescaleDB
sudo timescaledb-tune --quiet --yes

# Restart PostgreSQL
sudo systemctl restart postgresql
```

Then create the database:

```bash
sudo -u postgres psql <<EOF
-- Create database
CREATE DATABASE defi_apr_tracker;

-- Connect to database and enable TimescaleDB
\c defi_apr_tracker
CREATE EXTENSION IF NOT EXISTS timescaledb;
\q
EOF
```

**Option B: Without TimescaleDB (Simpler, works fine)**

```bash
sudo -u postgres psql <<EOF
CREATE DATABASE defi_apr_tracker;
\q
EOF
```

### Step 5: Configure database.yaml

Edit `config/database.yaml` and set your PostgreSQL password:

```bash
# The file should look like this:
nano config/database.yaml
```

Update the password field:
```yaml
database:
  host: localhost
  port: 5432
  database: defi_apr_tracker
  user: postgres
  password: your_actual_password_here  # Replace with the password you set in Step 3
```

### Step 6: Run Database Setup

Activate your virtual environment and run the setup script:

```bash
# Activate virtual environment
source venv/bin/activate

# Run database setup (with TimescaleDB)
python src/database/setup.py

# OR if you skipped TimescaleDB:
# python src/database/setup.py --no-timescaledb
```

This will:
- Create all database tables
- Set up indexes
- Configure TimescaleDB hypertable (if enabled)
- Initialize blockchains and protocols from config

### Step 7: Verify Installation

Test the connection:

```bash
# Test from command line
psql -U postgres -d defi_apr_tracker -c "SELECT version();"

# Or test from Python
python -c "from src.database.connection import DatabaseConnection; db = DatabaseConnection(); conn = db.get_connection(); print('Connected!'); db.return_connection(conn)"
```

## Quick Installation Script

You can also use the provided setup script (requires sudo):

```bash
sudo bash setup_postgres.sh
```

Then continue with Steps 5-7 above.

## Troubleshooting

### "password authentication failed"
- Check that the password in `config/database.yaml` matches the postgres user password
- Try resetting the password (Step 3)

### "extension timescaledb does not exist"
- TimescaleDB is not installed or not enabled
- Run setup with `--no-timescaledb` flag: `python src/database/setup.py --no-timescaledb`
- The system works fine without TimescaleDB - it's just an optimization

### "permission denied to create extension"
- You need superuser privileges
- Use the `postgres` user (which has superuser rights)
- Or skip TimescaleDB with `--no-timescaledb` flag

### "database does not exist"
- Create the database first (Step 4)
- Or check the database name in `config/database.yaml`

## Next Steps

Once PostgreSQL is installed and configured:

1. ✅ Database is ready
2. ✅ Tables are created
3. ✅ You can start collecting DeFi APR data
4. ✅ API endpoints will work with the database

