"""Flask API application with charting UI"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file (use absolute path to project root)
project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(project_root / ".env")

from flask import Flask, jsonify, render_template, request, redirect
from flask_cors import CORS
from flask_login import current_user, login_required
from datetime import datetime, timedelta
from src.database.connection import DatabaseConnection
from src.database.queries import DatabaseQueries, APYQueries
from src.database.user_queries import UserQueries
from src.auth import login_manager
from src.auth.routes import auth_bp, init_auth
from src.auth.email import mail
from src.api.portfolio_routes import portfolio_bp

app = Flask(__name__, 
            template_folder='../../templates',
            static_folder='../../static')

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Mail configuration (from environment variables)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@yieldlife.io')

CORS(app, supports_credentials=True)

# Initialize extensions
login_manager.init_app(app)
mail.init_app(app)

# Database connection
db = DatabaseConnection()
queries = DatabaseQueries(db)
apy_queries = APYQueries(db)
user_queries = UserQueries(db)

# Initialize auth module with database
init_auth(db)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(portfolio_bp)


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return user_queries.get_user_by_id(int(user_id))


# Make current_user available in templates
@app.context_processor
def inject_user():
    """Inject current_user into all templates"""
    return dict(current_user=current_user)

# ============================================
# Token Pair Normalization
# ============================================

# Tokens that should always be listed SECOND in a pair
QUOTE_TOKENS = {
    # Native chain tokens
    'ADA',
    # Stablecoins (USD-pegged)
    'USDM', 'USDA', 'USDC', 'USDT', 'DJED', 'iUSD', 'IUSD', 'DAI', 'BUSD',
    'USDC.e', 'USDT.e', 'USDT0',
    # Wrapped versions
    'wADA', 'WADA',
}

def normalize_pair(symbol: str) -> str:
    """Normalize token pair ordering for consistent comparison across DEXs.
    
    Rules:
    1. ADA should always be second (e.g., NIGHT-ADA not ADA-NIGHT)
    2. Stablecoins should be second (e.g., NIGHT-USDM not USDM-NIGHT)
    3. If both tokens are quote tokens, prefer ADA > stablecoins
    """
    # Try common separators
    for sep in ['-', '/', '_']:
        if sep in symbol:
            parts = symbol.split(sep)
            if len(parts) == 2:
                token_a, token_b = parts[0].strip(), parts[1].strip()
                
                a_is_quote = token_a.upper() in QUOTE_TOKENS
                b_is_quote = token_b.upper() in QUOTE_TOKENS
                
                # If first token is a quote token but second isn't, swap
                if a_is_quote and not b_is_quote:
                    return f"{token_b}-{token_a}"
                
                # If both are quote tokens, prioritize ADA as second
                if a_is_quote and b_is_quote:
                    if token_a.upper() == 'ADA':
                        return f"{token_b}-{token_a}"
                    # Keep as-is if token_b is ADA or neither is ADA
                    return f"{token_a}-{token_b}"
                
                # Normalize separator to dash
                return f"{token_a}-{token_b}"
    
    # Single token or no separator - return as-is
    return symbol

# ============================================
# API Endpoints for Charts
# ============================================

@app.route('/api/chains')
def api_get_chains():
    """Get list of all chains"""
    chains = queries.get_all_blockchains()
    return jsonify(chains)

@app.route('/api/<chain>/protocols')
def api_get_protocols(chain):
    """Get protocols for a specific chain"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.protocol_id, p.name, p.api_url
                FROM protocols p
                JOIN blockchains b ON p.blockchain_id = b.blockchain_id
                WHERE b.name = %s
                ORDER BY p.name
            """, (chain,))
            protocols = [{'id': r[0], 'name': r[1], 'api_url': r[2]} 
                        for r in cur.fetchall()]
        return jsonify(protocols)
    finally:
        db.return_connection(conn)

@app.route('/api/<chain>/<protocol>/assets')
def api_get_assets(chain, protocol):
    """Get assets for a specific protocol on a chain
    
    Query params:
        yield_type: Filter by yield type ('lp', 'supply', 'borrow')
    """
    yield_type = request.args.get('yield_type', default=None, type=str)
    
    # Note: Kinetic/Flare data hidden from UI but still collected
    if protocol == 'kinetic':
        return jsonify([])
    
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            # Other protocols use apr_snapshots
            query = """
                SELECT DISTINCT a.symbol, a.name, s.yield_type
                FROM apr_snapshots s
                JOIN assets a ON s.asset_id = a.asset_id
                JOIN protocols p ON s.protocol_id = p.protocol_id
                JOIN blockchains b ON s.blockchain_id = b.blockchain_id
                WHERE b.name = %s AND p.name = %s
            """
            params = [chain, protocol]
            if yield_type:
                query += " AND s.yield_type = %s"
                params.append(yield_type)
            query += " ORDER BY a.symbol"
            cur.execute(query, params)
            assets = [{'symbol': r[0], 'name': r[1], 'yield_type': r[2]} for r in cur.fetchall()]
        return jsonify(assets)
    finally:
        db.return_connection(conn)

@app.route('/api/<chain>/<protocol>/history')
def api_get_apr_history(chain, protocol):
    """Get APR history for a protocol
    
    Query params:
        days: Number of days of history (default: 30)
        asset: Filter by specific asset symbol
        yield_type: Filter by yield type ('lp', 'supply', 'borrow')
    """
    days = request.args.get('days', default=30, type=int)
    asset = request.args.get('asset', default=None, type=str)
    yield_type = request.args.get('yield_type', default=None, type=str)
    
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            # Note: Kinetic/Flare data hidden from UI but still collected
            # To re-enable, restore the kinetic_apy_snapshots query
            if protocol == 'kinetic':
                # Return empty for now - data is collected but hidden
                return jsonify([])
            else:
                # Other protocols use apr_snapshots
                query = """
                    SELECT 
                        a.symbol,
                        s.apr,
                        s.timestamp,
                        s.yield_type
                    FROM apr_snapshots s
                    JOIN assets a ON s.asset_id = a.asset_id
                    JOIN protocols p ON s.protocol_id = p.protocol_id
                    JOIN blockchains b ON s.blockchain_id = b.blockchain_id
                    WHERE b.name = %s 
                      AND p.name = %s
                      AND s.timestamp >= NOW() - %s * INTERVAL '1 day'
                """
                params = [chain, protocol, days]
                
                if asset:
                    query += " AND a.symbol = %s"
                    params.append(asset)
                
                if yield_type:
                    query += " AND s.yield_type = %s"
                    params.append(yield_type)
                
                query += " ORDER BY s.timestamp ASC"
            
            cur.execute(query, params)
            
            # Group by asset
            data = {}
            for row in cur.fetchall():
                symbol = row[0]
                apr_value = row[1]
                row_yield_type = row[3]
                if apr_value is None:
                    continue
                if symbol not in data:
                    data[symbol] = {'symbol': symbol, 'yield_type': row_yield_type, 'data': []}
                data[symbol]['data'].append({
                    'timestamp': row[2].isoformat(),
                    'apr': float(apr_value)
                })
            
        return jsonify(list(data.values()))
    finally:
        db.return_connection(conn)

@app.route('/api/<chain>/all/assets')
def api_get_all_assets_for_chain(chain):
    """Get all assets from all protocols on a chain
    
    Query params:
        yield_type: Filter by yield type ('lp', 'supply', 'borrow')
    
    Returns normalized pair names (e.g., NIGHT-ADA not ADA-NIGHT)
    """
    yield_type = request.args.get('yield_type', default=None, type=str)
    
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT DISTINCT a.symbol, a.name, p.name as protocol
                FROM apr_snapshots s
                JOIN assets a ON s.asset_id = a.asset_id
                JOIN protocols p ON s.protocol_id = p.protocol_id
                JOIN blockchains b ON s.blockchain_id = b.blockchain_id
                WHERE b.name = %s
            """
            params = [chain]
            
            if yield_type:
                query += " AND s.yield_type = %s"
                params.append(yield_type)
            
            query += " ORDER BY a.symbol, p.name"
            cur.execute(query, params)
            
            # Normalize pair names and deduplicate
            seen = set()
            assets = []
            for r in cur.fetchall():
                normalized = normalize_pair(r[0])
                if normalized not in seen:
                    seen.add(normalized)
                    assets.append({'symbol': normalized, 'name': r[1], 'protocol': r[2]})
            
            # Sort by normalized symbol
            assets.sort(key=lambda x: x['symbol'])
        return jsonify(assets)
    finally:
        db.return_connection(conn)

@app.route('/api/<chain>/all/history')
def api_get_all_history_for_chain(chain):
    """Get APR history from ALL protocols on a chain
    
    Query params:
        days: Number of days of history (default: 30)
        yield_type: Filter by yield type ('lp', 'supply', 'borrow')
    
    Returns data grouped by protocol and symbol for multi-DEX comparison
    """
    days = request.args.get('days', default=30, type=int)
    yield_type = request.args.get('yield_type', default=None, type=str)
    
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT 
                    p.name as protocol,
                    a.symbol,
                    s.apr,
                    s.timestamp,
                    s.yield_type,
                    s.tvl_usd,
                    s.version,
                    s.apr_1d,
                    s.fees_24h,
                    s.fee_apr,
                    s.staking_apr,
                    s.farm_apr,
                    s.swap_fee_percent,
                    s.volume_24h
                FROM apr_snapshots s
                JOIN assets a ON s.asset_id = a.asset_id
                JOIN protocols p ON s.protocol_id = p.protocol_id
                JOIN blockchains b ON s.blockchain_id = b.blockchain_id
                WHERE b.name = %s
                  AND s.timestamp >= NOW() - %s * INTERVAL '1 day'
            """
            params = [chain, days]
            
            if yield_type:
                query += " AND s.yield_type = %s"
                params.append(yield_type)
            
            query += " ORDER BY s.timestamp ASC"
            cur.execute(query, params)
            
            # Group by protocol, normalized symbol, and version
            data = {}
            for row in cur.fetchall():
                protocol = row[0]
                raw_symbol = row[1]
                apr_value = row[2]
                timestamp = row[3]
                row_yield_type = row[4]
                tvl_usd = row[5]
                version = row[6]
                apr_1d = row[7]
                fees_24h = row[8]
                fee_apr = row[9]
                staking_apr = row[10]
                farm_apr = row[11]
                swap_fee_percent = row[12]
                volume_24h = row[13]
                
                if apr_value is None:
                    continue
                
                # Normalize pair name for consistent grouping across DEXs
                symbol = normalize_pair(raw_symbol)
                
                # Key by protocol_symbol_version for unique lines (version can differentiate same pair)
                version_suffix = f"_{version}" if version else ""
                key = f"{protocol}_{symbol}{version_suffix}"
                if key not in data:
                    data[key] = {
                        'protocol': protocol,
                        'symbol': symbol,
                        'version': version,
                        'yield_type': row_yield_type,
                        'data': []
                    }
                data[key]['data'].append({
                    'timestamp': timestamp.isoformat(),
                    'apr': float(apr_value),
                    'tvl_usd': float(tvl_usd) if tvl_usd else None,
                    'apr_1d': float(apr_1d) if apr_1d else None,
                    'fees_24h': float(fees_24h) if fees_24h else None,
                    'fee_apr': float(fee_apr) if fee_apr else None,
                    'staking_apr': float(staking_apr) if staking_apr else None,
                    'farm_apr': float(farm_apr) if farm_apr else None,
                    'swap_fee_percent': float(swap_fee_percent) if swap_fee_percent else None,
                    'volume_24h': float(volume_24h) if volume_24h else None
                })
            
        return jsonify(list(data.values()))
    finally:
        db.return_connection(conn)

# ============================================
# Cross-chain Yield Type Endpoints
# ============================================

@app.route('/api/yields/<yield_type>')
def api_get_yields_by_type(yield_type):
    """Get all yields of a specific type across all chains
    
    Args:
        yield_type: 'lp', 'supply', or 'borrow'
        
    Query params:
        days: Number of days of history (default: 30)
    """
    if yield_type not in ('lp', 'supply', 'borrow'):
        return jsonify({'error': 'Invalid yield_type. Must be lp, supply, or borrow'}), 400
    
    days = request.args.get('days', default=30, type=int)
    
    conn = db.get_connection()
    try:
        results = []
        with conn.cursor() as cur:
            # Get from apr_snapshots (Minswap LPs, etc.)
            if yield_type == 'lp':
                cur.execute("""
                    SELECT 
                        b.name as chain,
                        p.name as protocol,
                        a.symbol,
                        s.apr,
                        s.timestamp,
                        s.yield_type,
                        s.apr_1d
                    FROM apr_snapshots s
                    JOIN assets a ON s.asset_id = a.asset_id
                    JOIN protocols p ON s.protocol_id = p.protocol_id
                    JOIN blockchains b ON s.blockchain_id = b.blockchain_id
                    WHERE s.yield_type = %s
                      AND s.timestamp >= NOW() - %s * INTERVAL '1 day'
                    ORDER BY s.timestamp ASC
                """, (yield_type, days))
                
                for row in cur.fetchall():
                    results.append({
                        'chain': row[0],
                        'protocol': row[1],
                        'symbol': row[2],
                        'apr': float(row[3]) if row[3] else None,
                        'timestamp': row[4].isoformat(),
                        'yield_type': row[5],
                        'apr_1d': float(row[6]) if row[6] else None
                    })
            
            # Note: Kinetic/Flare data is still collected but hidden from UI
            # To re-enable, uncomment the kinetic_apy_snapshots query below
            # if yield_type in ('supply', 'borrow'):
            #     cur.execute("""
            #         SELECT 
            #             'flare' as chain,
            #             'kinetic' as protocol,
            #             a.symbol,
            #             CASE 
            #                 WHEN %s = 'supply' THEN s.total_supply_apy
            #                 ELSE s.borrow_apy
            #             END as apr,
            #             s.timestamp,
            #             s.yield_type,
            #             s.market_type
            #         FROM kinetic_apy_snapshots s
            #         JOIN assets a ON s.asset_id = a.asset_id
            #         WHERE s.timestamp >= NOW() - INTERVAL '%s days'
            #         ORDER BY s.timestamp ASC
            #     """, (yield_type, days))
            #     
            #     for row in cur.fetchall():
            #         apr_value = row[3]
            #         if apr_value is None:
            #             continue
            #         results.append({
            #             'chain': row[0],
            #             'protocol': row[1],
            #             'symbol': row[2],
            #             'apr': float(apr_value),
            #             'timestamp': row[4].isoformat(),
            #             'yield_type': yield_type,
            #             'market_type': row[6]
            #         })
        
        # Group by chain/protocol/symbol
        grouped = {}
        for r in results:
            key = f"{r['chain']}_{r['protocol']}_{r['symbol']}"
            if key not in grouped:
                grouped[key] = {
                    'chain': r['chain'],
                    'protocol': r['protocol'],
                    'symbol': r['symbol'],
                    'yield_type': r['yield_type'],
                    'market_type': r.get('market_type'),
                    'data': []
                }
            grouped[key]['data'].append({
                'timestamp': r['timestamp'],
                'apr': r['apr'],
                'apr_1d': r.get('apr_1d')
            })
        
        return jsonify(list(grouped.values()))
    finally:
        db.return_connection(conn)

@app.route('/api/liqwid/lending')
def api_get_liqwid_lending():
    """Get Liqwid lending data with both supply and borrow rates

    Query params:
        days: Number of days of history (default: 7)

    Returns supply_apy, borrow_apy, and spread for each asset over time
    """
    days = request.args.get('days', default=7, type=int)

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    a.symbol,
                    s.total_supply_apy,
                    s.borrow_apy,
                    s.total_supply,
                    s.total_borrows,
                    s.utilization_rate,
                    s.timestamp
                FROM liqwid_apy_snapshots s
                JOIN assets a ON s.asset_id = a.asset_id
                WHERE s.timestamp >= NOW() - INTERVAL '1 day' * %s
                ORDER BY a.symbol, s.timestamp ASC
            """, (days,))

            # Group by asset
            data = {}
            for row in cur.fetchall():
                symbol = row[0]
                supply_apy = row[1]
                borrow_apy = row[2]
                total_supply = row[3]
                total_borrows = row[4]
                utilization = row[5]
                timestamp = row[6]

                if symbol not in data:
                    data[symbol] = {
                        'symbol': symbol,
                        'data': []
                    }

                # Calculate spread (borrow - supply)
                spread = None
                if supply_apy is not None and borrow_apy is not None:
                    spread = float(borrow_apy) - float(supply_apy)

                data[symbol]['data'].append({
                    'timestamp': timestamp.isoformat(),
                    'supply_apy': float(supply_apy) if supply_apy else None,
                    'borrow_apy': float(borrow_apy) if borrow_apy else None,
                    'spread': spread,
                    'total_supply': float(total_supply) if total_supply else None,
                    'total_borrows': float(total_borrows) if total_borrows else None,
                    'utilization': float(utilization) if utilization else None
                })

        return jsonify(list(data.values()))
    finally:
        db.return_connection(conn)


@app.route('/api/liqwid/lending/latest')
def api_get_liqwid_lending_latest():
    """Get latest Liqwid lending data for all assets

    Returns current supply_apy, borrow_apy, spread, and TVL for each asset
    Sorted by total_supply (TVL) descending to identify top collateral
    """
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (a.symbol)
                    a.symbol,
                    s.total_supply_apy,
                    s.borrow_apy,
                    s.total_supply,
                    s.total_borrows,
                    s.utilization_rate,
                    s.timestamp
                FROM liqwid_apy_snapshots s
                JOIN assets a ON s.asset_id = a.asset_id
                ORDER BY a.symbol, s.timestamp DESC
            """)

            results = []
            for row in cur.fetchall():
                supply_apy = row[1]
                borrow_apy = row[2]
                spread = None
                if supply_apy is not None and borrow_apy is not None:
                    spread = float(borrow_apy) - float(supply_apy)

                results.append({
                    'symbol': row[0],
                    'supply_apy': float(supply_apy) if supply_apy else None,
                    'borrow_apy': float(borrow_apy) if borrow_apy else None,
                    'spread': spread,
                    'total_supply': float(row[3]) if row[3] else None,
                    'total_borrows': float(row[4]) if row[4] else None,
                    'utilization': float(row[5]) if row[5] else None,
                    'timestamp': row[6].isoformat()
                })

        # Sort by total_supply (TVL) descending
        results.sort(key=lambda x: x['total_supply'] if x['total_supply'] else 0, reverse=True)

        return jsonify(results)
    finally:
        db.return_connection(conn)


@app.route('/api/yields/<yield_type>/latest')
def api_get_latest_yields_by_type(yield_type):
    """Get latest yields of a specific type across all chains (for dashboard cards)
    
    Args:
        yield_type: 'lp', 'supply', or 'borrow'
    """
    if yield_type not in ('lp', 'supply', 'borrow'):
        return jsonify({'error': 'Invalid yield_type. Must be lp, supply, or borrow'}), 400
    
    conn = db.get_connection()
    try:
        results = []
        with conn.cursor() as cur:
            # Get latest from apr_snapshots (LPs)
            if yield_type == 'lp':
                cur.execute("""
                    SELECT DISTINCT ON (a.symbol)
                        b.name as chain,
                        p.name as protocol,
                        a.symbol,
                        s.apr,
                        s.timestamp,
                        s.apr_1d
                    FROM apr_snapshots s
                    JOIN assets a ON s.asset_id = a.asset_id
                    JOIN protocols p ON s.protocol_id = p.protocol_id
                    JOIN blockchains b ON s.blockchain_id = b.blockchain_id
                    WHERE s.yield_type = %s
                    ORDER BY a.symbol, s.timestamp DESC
                """, (yield_type,))
                
                for row in cur.fetchall():
                    results.append({
                        'chain': row[0],
                        'protocol': row[1],
                        'symbol': row[2],
                        'apr': float(row[3]) if row[3] else None,
                        'timestamp': row[4].isoformat(),
                        'yield_type': yield_type,
                        'apr_1d': float(row[5]) if row[5] else None
                    })
            
            # Note: Kinetic/Flare data is still collected but hidden from UI
            # To re-enable, uncomment the kinetic_apy_snapshots query below
            # if yield_type in ('supply', 'borrow'):
            #     cur.execute("""
            #         SELECT DISTINCT ON (a.symbol)
            #             'flare' as chain,
            #             'kinetic' as protocol,
            #             a.symbol,
            #             CASE 
            #                 WHEN %s = 'supply' THEN s.total_supply_apy
            #                 ELSE s.borrow_apy
            #             END as apr,
            #             s.timestamp,
            #             s.market_type
            #         FROM kinetic_apy_snapshots s
            #         JOIN assets a ON s.asset_id = a.asset_id
            #         ORDER BY a.symbol, s.timestamp DESC
            #     """, (yield_type,))
            #     
            #     for row in cur.fetchall():
            #         apr_value = row[3]
            #         if apr_value is None:
            #             continue
            #         results.append({
            #             'chain': row[0],
            #             'protocol': row[1],
            #             'symbol': row[2],
            #             'apr': float(apr_value),
            #             'timestamp': row[4].isoformat(),
            #             'yield_type': yield_type,
            #             'market_type': row[5]
            #         })
        
        # Sort by APR descending
        results.sort(key=lambda x: x['apr'] if x['apr'] else 0, reverse=True)
        
        return jsonify(results)
    finally:
        db.return_connection(conn)

# ============================================
# Web Pages
# ============================================

@app.route('/')
def index():
    """Main landing page"""
    return render_template('index.html')

# Legacy routes - redirect to chain-specific pages
@app.route('/lps')
def lps_page():
    """Redirect to Cardano LPs (primary chain)"""
    return redirect('/cardano/lps')

@app.route('/earn')
def earn_page():
    """Redirect to Cardano lending"""
    return redirect('/cardano/lending')

@app.route('/borrow')
def borrow_page():
    """Redirect to Cardano lending (borrow rates shown there)"""
    return redirect('/cardano/lending')

@app.route('/cardano/lps')
def cardano_lps_page():
    """Cardano liquidity pools page"""
    return render_template('cardano_lps.html', chain='cardano', yield_type='lp')

@app.route('/cardano/lending')
def cardano_lending_page():
    """Cardano lending page"""
    return render_template('cardano_lending.html', chain='cardano', yield_type='supply')

@app.route('/embed/<chain>/<protocol>')
def embed_widget(chain, protocol):
    """Embeddable widget view"""
    asset = request.args.get('asset', default=None)
    days = request.args.get('days', default=30, type=int)
    return render_template('embed.html', 
                          chain=chain, 
                          protocol=protocol,
                          asset=asset,
                          days=days)

@app.route('/my-charts')
def my_charts_page():
    """User's saved charts page"""
    return render_template('my_charts.html')


@app.route('/portfolio')
@login_required
def portfolio_page():
    """User's portfolio page - requires wallet connection"""
    if not current_user.wallet_address:
        return redirect('/cardano/lps?error=wallet_required')
    return render_template('portfolio.html')

@app.route('/reset-password/<token>')
def reset_password_page(token):
    """Password reset page"""
    return render_template('reset_password.html', token=token)

# ============================================
# Legacy endpoints
# ============================================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200


if __name__ == '__main__':
    import os
    debug_mode = os.environ.get('FLASK_DEBUG', '1') == '1'
    use_reloader = os.environ.get('FLASK_RELOADER', '0') == '1'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000, use_reloader=use_reloader)
