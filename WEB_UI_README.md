# YieldLife - Cardano DeFi Yield Tracker Web UI

Interactive web interface for viewing historical APR data across Cardano DeFi protocols.

## Features

- 📊 **Interactive Charts** - View APR trends with Chart.js
- ♠️ **Cardano Focused** - Deep coverage of Cardano's top DEXs and lending protocols
- 🎨 **Embeddable Widgets** - Add charts to any website via iframe
- 📱 **Responsive Design** - Works on mobile and desktop
- 🎯 **Filtering** - Time range, asset, and protocol selection

## Quick Start

### Run Locally

```bash
# Start the Flask server
./run_web.sh

# Or manually:
source venv/bin/activate
python src/api/app.py
```

Then visit:
- **Main page:** http://localhost:5000
- **Cardano:** http://localhost:5000/chain/cardano
- **Liquidity Pools:** http://localhost:5000/lps
- **Liqwid Lending:** http://localhost:5000/earn

## Pages

### Home Page (`/`)
Landing page with protocol cards and quick links.

### Cardano Page (`/chain/cardano`)
Interactive charts for all Cardano protocols:
- Minswap, SundaeSwap, WingRiders LP pools
- Multi-DEX comparison on single charts

Features:
- Time range selector (7/30/90/365 days)
- Asset filter (individual or all)
- Protocol comparison
- Current APR summary cards

### Embed Widget (`/embed/<chain>/<protocol>`)
Minimal embeddable charts for external sites.

Example:
```
http://localhost:5000/embed/cardano/minswap?asset=NIGHT-ADA&days=30
```

## API Endpoints

### Public Data APIs

```
GET /api/chains
    Returns: List of all blockchains

GET /api/<chain>/protocols
    Returns: Protocols for a specific chain

GET /api/<chain>/<protocol>/assets
    Returns: Assets tracked for a protocol

GET /api/<chain>/<protocol>/history?days=30&asset=NIGHT-ADA
    Returns: Historical APR data
    Params:
        - days: Number of days to fetch (default: 30)
        - asset: Filter by specific asset (optional)
```

## Embedding Widgets

### Option 1: Iframe (Simple)

Add this to your HTML:

```html
<iframe 
  src="http://localhost:5000/embed/cardano/minswap?asset=NIGHT-ADA&days=30" 
  width="100%" 
  height="400" 
  frameborder="0">
</iframe>
```

### Option 2: JavaScript Widget (Advanced)

Create `static/widget.js`:

```javascript
(function() {
  window.DefiAprWidget = {
    create: function(containerId, options) {
      const iframe = document.createElement('iframe');
      iframe.src = `${options.baseUrl}/embed/${options.chain}/${options.protocol}?asset=${options.asset || ''}&days=${options.days || 30}`;
      iframe.style.width = options.width || '100%';
      iframe.style.height = options.height || '400px';
      iframe.style.border = 'none';
      document.getElementById(containerId).appendChild(iframe);
    }
  };
})();
```

Usage:

```html
<div id="apr-widget"></div>
<script src="http://yourdomain.com/static/widget.js"></script>
<script>
  DefiAprWidget.create('apr-widget', {
    baseUrl: 'http://yourdomain.com',
    chain: 'cardano',
    protocol: 'minswap',
    asset: 'NIGHT-ADA',
    days: 30
  });
</script>
```

## Design Customization

Edit `templates/base.html` CSS variables:

```css
:root {
    --flare-color: #e84142;
    --cardano-color: #0033ad;
    --primary-bg: #1a1d29;      /* Dark background */
    --secondary-bg: #252938;    /* Card background */
    --text-primary: #ffffff;
    --text-secondary: #b0b3c1;
}
```

### Theme Options

**Light Theme:**
```css
--primary-bg: #ffffff;
--secondary-bg: #f8f9fa;
--text-primary: #1a1d29;
--text-secondary: #6c757d;
```

**Crypto Dark:**
```css
--primary-bg: #0a0e27;
--secondary-bg: #141b3d;
```

## Technology Stack

- **Backend:** Flask + Python 3.9
- **Database:** PostgreSQL with TimescaleDB
- **Frontend:** Bootstrap 5 + Chart.js 4
- **Charts:** Chart.js with date-fns adapter
- **Styling:** Custom CSS with CSS variables

## Development

### Project Structure

```
├── src/api/app.py           # Flask application
├── templates/
│   ├── base.html            # Base template with navbar
│   ├── index.html           # Landing page
│   ├── chain.html           # Chain-specific charts
│   └── embed.html           # Embeddable widget
├── static/                  # Static assets (optional)
└── run_web.sh              # Startup script
```

### Adding New Cardano Protocols

1. Create a collection script in `scripts/`
2. Add protocol to `config/chains.yaml`
3. Add protocol logo to `static/`
4. Update `protocolLogos` in templates

## Production Deployment

### Option 1: Gunicorn (Recommended)

```bash
pip install gunicorn

gunicorn -w 4 -b 0.0.0.0:5000 src.api.app:app
```

### Option 2: Docker

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "src.api.app:app"]
```

### Option 3: Raspberry Pi with Nginx

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## CORS Configuration

For external widget embeds, CORS is enabled by default. To restrict origins in production:

```python
from flask_cors import CORS

CORS(app, resources={
    r"/api/*": {"origins": ["https://yourdomain.com"]},
    r"/embed/*": {"origins": "*"}  # Allow all for embeds
})
```

## Troubleshooting

### Charts not loading
- Check browser console for API errors
- Verify database has data: `psql -d defitracker -c "SELECT COUNT(*) FROM apr_snapshots;"`
- Ensure Flask server is running

### Embed widget blank
- Check iframe src URL is accessible
- Verify CORS headers are set
- Test embed URL directly in browser

### No data for chain
- Run collection script: `python scripts/collect_minswap_apr.py`
- Check database connections in `config/database.yaml`

## Support

For issues or questions, check:
- Database schema: `DATABASE_SCHEMA.md`
- Collection scripts: `CRON_SETUP.md`
- API code: `src/api/app.py`

