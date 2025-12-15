# Multi-Chain DeFi APR Tracker

A Python-based system for tracking APR (Annual Percentage Rate) data across multiple blockchain networks, starting with Flare. The system collects daily APR data from various DeFi protocols, stores it in PostgreSQL/TimescaleDB, and provides a REST API and web interface for visualization.

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
   copy config\database.yaml.template config\database.yaml
   # Edit config\database.yaml with your PostgreSQL credentials
   ```

4. **Set up database:**
   ```bash
   python src\database\setup.py
   ```

5. **Start the API:**
   ```bash
   python src\api\app.py
   ```

See [DATABASE_SETUP_GUIDE.md](DATABASE_SETUP_GUIDE.md) for detailed database setup instructions.

## Architecture

- **Multi-chain support**: Extensible architecture to add new blockchains easily
- **Hybrid data fetching**: Prefers protocol APIs when available, falls back to on-chain computation
- **Time-series storage**: Uses TimescaleDB for efficient historical data storage
- **Scheduled collection**: Daily automated data collection via APScheduler

## Project Structure

```
DefiTracker/
├── src/
│   ├── adapters/          # Chain and protocol adapters
│   │   ├── base.py        # Base abstract classes
│   │   └── flare/         # Flare chain implementation
│   ├── collectors/        # Data collection logic
│   ├── database/          # Database models and queries
│   ├── api/               # REST API endpoints
│   └── scheduler/         # Scheduled tasks
├── config/
│   ├── chains.yaml        # Chain registry configuration
│   └── database.yaml      # Database configuration
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

4. Run the collector:
```bash
python src/collectors/main.py
```

5. Start the API server:
```bash
python src/api/app.py
```

## APR Calculation

The system uses the following formula for APR calculation:

\[APR \approx \frac{\text{rewards over period}}{\text{average supplied over period}} \times \frac{365}{\text{days in period}}\]

## License

MIT
