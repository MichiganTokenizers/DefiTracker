# Database Setup Guide - Windows

## 💰 Cost: $0.00 (Completely FREE)

**Everything in this setup is 100% FREE:**
- ✅ **PostgreSQL**: Free, open-source database
- ✅ **TimescaleDB**: Free, open-source extension (no subscription, no fees)
- ✅ **All operations**: Free
- ✅ **No cloud services**: Everything runs locally on your Windows machine
- ✅ **No monthly fees**: Ever
- ✅ **No data limits**: Only limited by your disk space

**You are NOT introducing any costs.** TimescaleDB is not a paid service - it's a free PostgreSQL extension you install locally, just like any other software.

### About TimescaleDB

- **What it is**: A free, open-source PostgreSQL extension that optimizes time-series data
- **Cost**: $0.00 (completely free)
- **Subscription**: None needed
- **Installation**: Download and install locally (like any other software)
- **Superuser requirement**: Creating the extension needs admin privileges (one-time setup)
- **Can you skip it?**: Yes! The system works perfectly without TimescaleDB - it's just an optimization

**If you don't have superuser access or want to skip it:** Just run the setup with `--no-timescaledb` flag. Everything will work fine.

## Prerequisites

1. **PostgreSQL** (version 12 or higher) - FREE
2. **TimescaleDB extension** (optional, FREE, but needs superuser to enable)
3. Python dependencies installed (`pip install -r requirements.txt`)

## Step-by-Step Setup (Windows)

### Step 1: Install PostgreSQL

1. Download PostgreSQL from https://www.postgresql.org/download/windows/
2. Run the installer (e.g., `postgresql-16.x-windows-x64.exe`)
3. During installation:
   - Choose installation directory (default is fine)
   - **Important:** Set a password for the `postgres` superuser account - remember this!
   - Port: 5432 (default)
   - Locale: Default
4. Complete the installation
5. PostgreSQL will start automatically as a Windows service

**Verify installation:**
- Open Command Prompt or PowerShell
- Navigate to PostgreSQL bin directory (usually `C:\Program Files\PostgreSQL\16\bin`)
- Or add it to your PATH
- Test: `psql --version`

### Step 2: Install TimescaleDB (Optional - FREE)

**TimescaleDB is completely free** - it's an open-source extension. No subscription needed.

**Option A: With Superuser Access (Recommended)**
If you installed PostgreSQL yourself, you ARE the superuser. You can enable TimescaleDB:

1. Download TimescaleDB for Windows from: https://docs.timescale.com/install/latest/self-hosted/installation-windows/
2. Run the installer
3. It will detect your PostgreSQL installation automatically
4. Follow the installation prompts

**Option B: Without Superuser Access (Also Fine)**
If you don't have superuser access or want to skip TimescaleDB:
- **The system works perfectly without it!**
- Just use regular PostgreSQL
- Run setup with `--no-timescaledb` flag
- You'll still get all functionality, just without time-series optimizations

### Step 3: Create Database (Windows)

**Using Command Prompt or PowerShell:**

1. Open Command Prompt or PowerShell
2. Navigate to PostgreSQL bin directory:
   ```cmd
   cd "C:\Program Files\PostgreSQL\16\bin"
   ```
   (Replace `16` with your PostgreSQL version)

3. Connect to PostgreSQL:
   ```cmd
   psql -U postgres
   ```
   Enter the password you set during installation

4. In the `psql` prompt, create the database:
   ```sql
   CREATE DATABASE defi_apr_tracker;
   \c defi_apr_tracker
   ```

5. **If you have superuser access** (you installed PostgreSQL yourself), enable TimescaleDB:
   ```sql
   CREATE EXTENSION IF NOT EXISTS timescaledb;
   ```

6. Exit:
   ```sql
   \q
   ```

**Alternative: Using pgAdmin (GUI)**
1. Open pgAdmin (installed with PostgreSQL)
2. Connect to your PostgreSQL server
3. Right-click "Databases" → "Create" → "Database"
4. Name: `defi_apr_tracker`
5. Click "Save"

**Note:** If you skip TimescaleDB, the system works perfectly fine - it's just an optimization.

### Step 4: Configure Database Connection

Edit `config/database.yaml`:

```yaml
database:
  host: localhost
  port: 5432
  database: defi_apr_tracker
  user: postgres
  password: your_actual_password_here
```

**Security Note:** For production, use environment variables instead of storing passwords in files:

```python
# In connection.py, you can modify to read from environment:
password = os.getenv('DB_PASSWORD', self.db_config.get('password'))
```

### Step 5: Run Database Setup Script

Run the setup script to create all tables and schema:

```bash
python src/database/setup.py
```

This will:
1. Create all tables (blockchains, protocols, assets, apr_snapshots, collection_logs)
2. Create indexes
3. Set up TimescaleDB hypertable (if you have permissions)
4. Initialize blockchains and protocols from `config/chains.yaml`

**If you don't have superuser access for TimescaleDB:**

```bash
python src/database/setup.py --no-timescaledb
```

This will create the tables without the TimescaleDB hypertable. You can convert it later when you have superuser access.

### Step 6: Verify Setup (Windows)

The setup script automatically verifies the setup, but you can also manually check:

**Using Command Prompt:**
```cmd
cd "C:\Program Files\PostgreSQL\16\bin"
psql -U postgres -d defi_apr_tracker
```

**In psql prompt:**
```sql
-- Check tables
\dt

-- Check if TimescaleDB is working (if enabled)
SELECT * FROM timescaledb_information.hypertables;

-- Check blockchains
SELECT * FROM blockchains;

-- Check protocols
SELECT * FROM protocols;
```

**Or use pgAdmin:**
- Open pgAdmin
- Navigate to `defi_apr_tracker` database
- Expand "Schemas" → "public" → "Tables"
- You should see: blockchains, protocols, assets, apr_snapshots, collection_logs

## Manual Setup (Alternative - Windows)

If you prefer to run SQL manually:

1. **Run initial schema:**
   ```cmd
   cd "C:\Program Files\PostgreSQL\16\bin"
   psql -U postgres -d defi_apr_tracker -f "C:\path\to\your\project\migrations\001_initial_schema.sql"
   ```
   (Replace with your actual project path)

2. **Set up TimescaleDB (if you have superuser access):**
   ```cmd
   psql -U postgres -d defi_apr_tracker -f "C:\path\to\your\project\migrations\002_setup_timescaledb.sql"
   ```

3. **Initialize data from config:**
   ```cmd
   python -c "from src.database.setup import initialize_from_config; initialize_from_config()"
   ```

## Cost Breakdown: $0.00

**Everything is FREE:**
- ✅ PostgreSQL: Free and open source
- ✅ TimescaleDB: Free and open source (no subscription)
- ✅ All database operations: Free
- ✅ No cloud services required
- ✅ No monthly fees
- ✅ No data limits (limited only by your disk space)

**You're running everything locally on your Windows machine - zero ongoing costs.**

## Troubleshooting (Windows)

### Error: "extension timescaledb does not exist"
- TimescaleDB is not installed or not enabled
- **Solution:** Run setup with `--no-timescaledb` flag - the system works fine without it
- Or install TimescaleDB following Step 2 (it's free)

### Error: "permission denied to create extension"
- You need superuser (postgres) privileges
- **If you installed PostgreSQL yourself:** You ARE the superuser - use the `postgres` user
- **If you don't have superuser access:** Skip TimescaleDB with `--no-timescaledb` flag
- **The system works perfectly without TimescaleDB** - it's just an optimization

### Error: "password authentication failed"
- Check `config/database.yaml` has correct password
- Or set `PGPASSWORD` environment variable in PowerShell:
  ```powershell
  $env:PGPASSWORD="your_password"
  ```

### Error: "psql is not recognized"
- PostgreSQL bin directory is not in your PATH
- **Solution:** Use full path: `"C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres`
- Or add PostgreSQL bin to your Windows PATH environment variable

### Error: "database does not exist"
- Create the database first (Step 3)
- Or update `config/database.yaml` with correct database name

### Error: "relation already exists"
- Tables already exist from previous setup
- This is fine, the setup script handles this
- If you want to start fresh (in psql):
  ```sql
  DROP TABLE IF EXISTS apr_snapshots CASCADE;
  DROP TABLE IF EXISTS collection_logs CASCADE;
  DROP TABLE IF EXISTS assets CASCADE;
  DROP TABLE IF EXISTS protocols CASCADE;
  DROP TABLE IF EXISTS blockchains CASCADE;
  ```

## Schema Overview

After setup, you'll have:

1. **blockchains** - List of blockchain networks
2. **protocols** - DeFi protocols per blockchain
3. **assets** - Token/asset information
4. **apr_snapshots** - Time-series APR data (TimescaleDB hypertable)
5. **collection_logs** - Collection job tracking

## Next Steps

Once the database is set up:

1. **Test the connection:**
   ```python
   from src.database.connection import DatabaseConnection
   db = DatabaseConnection()
   conn = db.get_connection()
   print("Connected successfully!")
   db.return_connection(conn)
   ```

2. **Test queries:**
   ```python
   from src.database.queries import DatabaseQueries
   queries = DatabaseQueries()
   blockchains = queries.get_all_blockchains()
   print(blockchains)
   ```

3. **Start collecting data:**
   - The scheduler will automatically store APR data
   - Or manually insert test data to verify

## Production Considerations

1. **Connection Pooling:** Already implemented in `DatabaseConnection`
2. **Backups:** Set up regular PostgreSQL backups
3. **Monitoring:** Monitor table sizes and query performance
4. **Indexes:** Already created, but monitor for additional needs
5. **Retention:** Consider setting up TimescaleDB retention policies for old data
6. **Security:** Use environment variables for passwords, restrict database access

