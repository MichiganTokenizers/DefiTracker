"""Flask API application with charting UI"""
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from datetime import datetime, timedelta
from src.database.connection import DatabaseConnection
from src.database.queries import DatabaseQueries, APYQueries

app = Flask(__name__, 
            template_folder='../../templates',
            static_folder='../../static')
CORS(app)

db = DatabaseConnection()
queries = DatabaseQueries(db)
apy_queries = APYQueries(db)

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
    
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            # Kinetic uses kinetic_apy_snapshots table
            if protocol == 'kinetic':
                query = """
                    SELECT DISTINCT a.symbol, a.name, s.yield_type
                    FROM kinetic_apy_snapshots s
                    JOIN assets a ON s.asset_id = a.asset_id
                """
                params = []
                if yield_type:
                    query += " WHERE s.yield_type = %s"
                    params.append(yield_type)
                query += " ORDER BY a.symbol"
                cur.execute(query, params)
            else:
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
            # Kinetic uses kinetic_apy_snapshots table with total_supply_apy
            if protocol == 'kinetic':
                query = """
                    SELECT 
                        a.symbol,
                        s.total_supply_apy,
                        s.timestamp,
                        s.yield_type
                    FROM kinetic_apy_snapshots s
                    JOIN assets a ON s.asset_id = a.asset_id
                    WHERE s.timestamp >= NOW() - INTERVAL '%s days'
                """
                params = [days]
                
                if asset:
                    query += " AND a.symbol = %s"
                    params.append(asset)
                
                if yield_type:
                    query += " AND s.yield_type = %s"
                    params.append(yield_type)
                
                query += " ORDER BY s.timestamp ASC"
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
                      AND s.timestamp >= NOW() - INTERVAL '%s days'
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
                        s.yield_type
                    FROM apr_snapshots s
                    JOIN assets a ON s.asset_id = a.asset_id
                    JOIN protocols p ON s.protocol_id = p.protocol_id
                    JOIN blockchains b ON s.blockchain_id = b.blockchain_id
                    WHERE s.yield_type = %s
                      AND s.timestamp >= NOW() - INTERVAL '%s days'
                    ORDER BY s.timestamp ASC
                """, (yield_type, days))
                
                for row in cur.fetchall():
                    results.append({
                        'chain': row[0],
                        'protocol': row[1],
                        'symbol': row[2],
                        'apr': float(row[3]) if row[3] else None,
                        'timestamp': row[4].isoformat(),
                        'yield_type': row[5]
                    })
            
            # Get from kinetic_apy_snapshots (lending markets)
            if yield_type in ('supply', 'borrow'):
                cur.execute("""
                    SELECT 
                        'flare' as chain,
                        'kinetic' as protocol,
                        a.symbol,
                        CASE 
                            WHEN %s = 'supply' THEN s.total_supply_apy
                            ELSE s.borrow_apy
                        END as apr,
                        s.timestamp,
                        s.yield_type,
                        s.market_type
                    FROM kinetic_apy_snapshots s
                    JOIN assets a ON s.asset_id = a.asset_id
                    WHERE s.timestamp >= NOW() - INTERVAL '%s days'
                    ORDER BY s.timestamp ASC
                """, (yield_type, days))
                
                for row in cur.fetchall():
                    apr_value = row[3]
                    if apr_value is None:
                        continue
                    results.append({
                        'chain': row[0],
                        'protocol': row[1],
                        'symbol': row[2],
                        'apr': float(apr_value),
                        'timestamp': row[4].isoformat(),
                        'yield_type': yield_type,
                        'market_type': row[6]
                    })
        
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
                'apr': r['apr']
            })
        
        return jsonify(list(grouped.values()))
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
                        s.timestamp
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
                        'yield_type': yield_type
                    })
            
            # Get latest from kinetic_apy_snapshots (lending)
            if yield_type in ('supply', 'borrow'):
                cur.execute("""
                    SELECT DISTINCT ON (a.symbol)
                        'flare' as chain,
                        'kinetic' as protocol,
                        a.symbol,
                        CASE 
                            WHEN %s = 'supply' THEN s.total_supply_apy
                            ELSE s.borrow_apy
                        END as apr,
                        s.timestamp,
                        s.market_type
                    FROM kinetic_apy_snapshots s
                    JOIN assets a ON s.asset_id = a.asset_id
                    ORDER BY a.symbol, s.timestamp DESC
                """, (yield_type,))
                
                for row in cur.fetchall():
                    apr_value = row[3]
                    if apr_value is None:
                        continue
                    results.append({
                        'chain': row[0],
                        'protocol': row[1],
                        'symbol': row[2],
                        'apr': float(apr_value),
                        'timestamp': row[4].isoformat(),
                        'yield_type': yield_type,
                        'market_type': row[5]
                    })
        
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

@app.route('/chain/<chain_name>')
def chain_page(chain_name):
    """Chain-specific page with all protocols"""
    return render_template('chain.html', chain=chain_name)

@app.route('/lps')
def lps_page():
    """Liquidity Pools yield page"""
    return render_template('yield_type.html', 
                          yield_type='lp',
                          title='Liquidity Pools',
                          icon='🌊',
                          description='Provide liquidity to DEXs and earn trading fees + rewards')

@app.route('/earn')
def earn_page():
    """Lending supply yield page"""
    return render_template('yield_type.html', 
                          yield_type='supply',
                          title='Earn (Lend)',
                          icon='💰',
                          description='Supply assets to lending markets and earn interest')

@app.route('/borrow')
def borrow_page():
    """Borrow rates page"""
    return render_template('yield_type.html', 
                          yield_type='borrow',
                          title='Borrow Rates',
                          icon='🏦',
                          description='Compare borrowing costs across lending markets')

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

# ============================================
# Legacy endpoints
# ============================================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
