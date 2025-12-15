#!/bin/bash
# PostgreSQL Setup Script for DefiTracker
# This script installs PostgreSQL and sets up the database

set -e

echo "=== DefiTracker PostgreSQL Setup ==="
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "This script needs sudo privileges to install PostgreSQL."
    echo "Please run: sudo bash setup_postgres.sh"
    exit 1
fi

# Detect Linux distribution
if [ -f /etc/debian_version ]; then
    DISTRO="debian"
elif [ -f /etc/redhat-release ]; then
    DISTRO="redhat"
else
    echo "Unsupported Linux distribution. Please install PostgreSQL manually."
    exit 1
fi

echo "Detected distribution: $DISTRO"
echo ""

# Install PostgreSQL
if [ "$DISTRO" == "debian" ]; then
    echo "Installing PostgreSQL..."
    apt-get update
    apt-get install -y postgresql postgresql-contrib
    
    # Install TimescaleDB repository
    echo "Setting up TimescaleDB repository..."
    sh -c "echo 'deb https://packagecloud.io/timescale/timescaledb/debian/ $(lsb_release -c -s) main' > /etc/apt/sources.list.d/timescaledb.list"
    wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | apt-key add -
    apt-get update
    apt-get install -y timescaledb-2-postgresql-$(psql --version | grep -oP '\d+' | head -1)
    
    echo "Configuring TimescaleDB..."
    timescaledb-tune --quiet --yes
    
elif [ "$DISTRO" == "redhat" ]; then
    echo "Installing PostgreSQL..."
    yum install -y postgresql-server postgresql-contrib
    postgresql-setup --initdb
    systemctl enable postgresql
    systemctl start postgresql
fi

# Start PostgreSQL service
echo "Starting PostgreSQL service..."
systemctl enable postgresql
systemctl start postgresql

# Wait for PostgreSQL to be ready
sleep 2

# Create database and user
echo "Creating database and user..."
sudo -u postgres psql <<EOF
-- Create database
CREATE DATABASE defi_apr_tracker;

-- Create user (optional, can use postgres user)
-- CREATE USER defitracker WITH PASSWORD 'your_password_here';
-- GRANT ALL PRIVILEGES ON DATABASE defi_apr_tracker TO defitracker;

-- Connect to database and enable TimescaleDB
\c defi_apr_tracker
CREATE EXTENSION IF NOT EXISTS timescaledb;
\q
EOF

echo ""
echo "=== PostgreSQL Setup Complete ==="
echo ""
echo "Database created: defi_apr_tracker"
echo ""
echo "Next steps:"
echo "1. Create config/database.yaml from the template"
echo "2. Update the password in config/database.yaml"
echo "3. Run: python src/database/setup.py"
echo ""

