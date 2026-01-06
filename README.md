# YieldLife - Cardano DeFi Yield Tracker

A Python-based system for tracking APR/APY data across Cardano DeFi protocols. The system collects daily yield data from various DEXs and lending protocols, stores it in PostgreSQL/TimescaleDB, and provides a REST API and web interface for visualization.

## Supported Protocols

- **Minswap** - Liquidity pool farming APRs
- **SundaeSwap** - Liquidity pool farming APRs
- **WingRiders** - Liquidity pool farming APRs
- **Liqwid** - Lending supply/borrow rates

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/DefiTracker.git
   cd DefiTracker
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure database:**
   ```bash
   # Copy the template
   cp config/database.yaml.template config/database.yaml
   # Edit config/database.yaml with your PostgreSQL credentials
   ```

4. **Set up database:**
   ```bash
   python src/database/setup.py
   ```

5. **Start the web app:**
   ```bash
   python src/api/app.py
   ```

See [DATABASE_SETUP_GUIDE.md](DATABASE_SETUP_GUIDE.md) for detailed database setup instructions.

## Architecture

- **Cardano-focused**: Deep coverage of Cardano's top DeFi protocols
- **API-based data fetching**: Uses protocol APIs for accurate, real-time data
- **Time-series storage**: Uses TimescaleDB for efficient historical data storage
- **Scheduled collection**: Daily automated data collection via cron/APScheduler

## Project Structure

```
DefiTracker/
├── src/
│   ├── adapters/          # Chain and protocol adapters
│   │   ├── base.py        # Base abstract classes
│   │   └── cardano/       # Cardano protocol implementations
│   ├── collectors/        # Data collection logic
│   ├── database/          # Database models and queries
│   ├── api/               # REST API and web UI
│   └── scheduler/         # Scheduled tasks
├── scripts/               # Collection scripts
│   ├── collect_minswap_apr.py
│   ├── collect_sundaeswap_apr.py
│   ├── collect_wingriders_apr.py
│   └── collect_liqwid_apy.py
├── config/
│   ├── chains.yaml        # Chain registry configuration
│   └── database.yaml      # Database configuration
├── templates/             # Web UI templates
├── static/                # Static assets
├── requirements.txt
└── README.md
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure database connection in `config/database.yaml`

3. Configure chains in `config/chains.yaml`

4. Run collectors:
```bash
python scripts/collect_minswap_apr.py
python scripts/collect_sundaeswap_apr.py
python scripts/collect_wingriders_apr.py
python scripts/collect_liqwid_apy.py
```

5. Start the web server:
```bash
python src/api/app.py
```

## APR Calculation

Each protocol provides APR data via their APIs. The system normalizes and stores these values for historical tracking and comparison.

## License

MIT
