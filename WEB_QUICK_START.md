# Web UI Quick Start Guide

## 🚀 Start the Server

```bash
./run_web.sh
```

Or manually:
```bash
cd /home/danladuke/Projects/DefiTracker
source venv/bin/activate
export PYTHONPATH=/home/danladuke/Projects/DefiTracker:$PYTHONPATH
python src/api/app.py
```

## 🌐 Access the UI

Open your browser and visit:

### Main Pages
- **Home:** http://localhost:5000
- **Cardano:** http://localhost:5000/chain/cardano
- **Liquidity Pools:** http://localhost:5000/lps
- **Liqwid Lending:** http://localhost:5000/earn

### API Endpoints (for testing)
- **Health Check:** http://localhost:5000/health
- **All Chains:** http://localhost:5000/api/chains
- **Cardano Assets:** http://localhost:5000/api/cardano/minswap/assets
- **History:** http://localhost:5000/api/cardano/minswap/history?days=7&asset=NIGHT-ADA

### Embed Widget Example
http://localhost:5000/embed/cardano/minswap?asset=NIGHT-ADA&days=30

## 📊 What You Can Do

### View Historical APR Charts
1. Navigate to the Cardano page or strategy pages (LPs, Earn)
2. Use filters:
   - **Time Range:** 7/30/90/365 days
   - **Asset Filter:** Select specific asset or view all
   - **Chart Type:** Line or Bar chart
3. Hover over charts for detailed tooltips

### Embed Widgets
1. Click "Embed" in navbar
2. Copy the iframe code
3. Paste into any website

Example embed code:
```html
<iframe 
  src="http://localhost:5000/embed/cardano/minswap?asset=NIGHT-ADA&days=30" 
  width="100%" 
  height="400" 
  frameborder="0">
</iframe>
```

## 🛠 Testing the Setup

### Test API Endpoints
```bash
# Health check
curl http://localhost:5000/health

# Get all chains
curl http://localhost:5000/api/chains

# Get Minswap pools
curl http://localhost:5000/api/cardano/minswap/assets

# Get history
curl "http://localhost:5000/api/cardano/minswap/history?days=7&asset=NIGHT-ADA"
```

### Test in Browser
1. Visit http://localhost:5000
2. Click a Cardano protocol card
3. Select different time ranges
4. Filter by specific asset
5. Try different chart types

## 📱 Features Checklist

- ✅ Interactive charts with Chart.js
- ✅ Cardano-focused DeFi coverage
- ✅ Multiple protocols (Minswap, SundaeSwap, WingRiders, Liqwid)
- ✅ Time range filtering (7/30/90/365 days)
- ✅ Asset filtering (individual or all)
- ✅ Current APR summary cards
- ✅ Embeddable widgets
- ✅ Responsive design

## 🎨 Customization

### Change Theme Colors
Edit `templates/base.html`, CSS variables section:

```css
:root {
    --cardano-color: #0033ad;     /* Cardano badge color */
    --primary-bg: var(--sand-dune);  /* Main background */
    --text-primary: var(--carbon-black);
    --text-secondary: #4a4a4a;
}
```

## 🐛 Troubleshooting

### Server won't start
- Check database is running: `systemctl status postgresql`
- Verify config: `cat config/database.yaml`
- Check logs in terminal

### No data showing
- Run collection scripts:
  ```bash
  python scripts/collect_minswap_apr.py
  python scripts/collect_sundaeswap_apr.py
  python scripts/collect_wingriders_apr.py
  python scripts/collect_liqwid_apy.py
  ```
- Verify data in database:
  ```sql
  psql -d defitracker -c "SELECT COUNT(*) FROM apr_snapshots;"
  ```

### Charts not loading
- Check browser console (F12)
- Verify API returns data:
  ```bash
  curl "http://localhost:5000/api/cardano/minswap/history?days=7"
  ```

### Port 5000 already in use
- Find process: `lsof -i :5000`
- Kill it: `kill -9 <PID>`
- Or change port in `src/api/app.py`

## 📚 Documentation

- Full docs: `WEB_UI_README.md`
- Database schema: `DATABASE_SCHEMA.md`
- Data collection: `CRON_SETUP.md`

## 🚀 Next Steps

1. **Add more data** - Run collection scripts daily
2. **Deploy to production** - See `WEB_UI_README.md` for deployment options
3. **Customize design** - Edit CSS in `templates/base.html`
4. **Share widgets** - Use embed functionality on other sites

## 🎯 Current Status

✅ **Working:**
- Flask server running on port 5000
- All API endpoints functional
- Charts displaying historical data
- Embeddable widgets ready

📊 **Cardano Protocols Tracked:**
- Minswap: 35+ pools with APR history
- SundaeSwap: Liquidity pools
- WingRiders: Liquidity pools
- Liqwid: Lending supply rates
- Daily snapshots from automated runs

🔄 **To Do:**
- Deploy to public server
- Expand Cardano protocol coverage

