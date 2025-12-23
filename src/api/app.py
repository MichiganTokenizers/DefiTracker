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
    """Get assets for a specific protocol on a chain"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT a.symbol, a.name
                FROM apr_snapshots s
                JOIN assets a ON s.asset_id = a.asset_id
                JOIN protocols p ON s.protocol_id = p.protocol_id
                JOIN blockchains b ON s.blockchain_id = b.blockchain_id
                WHERE b.name = %s AND p.name = %s
                ORDER BY a.symbol
            """, (chain, protocol))
            assets = [{'symbol': r[0], 'name': r[1]} for r in cur.fetchall()]
        return jsonify(assets)
    finally:
        db.return_connection(conn)

@app.route('/api/<chain>/<protocol>/history')
def api_get_apr_history(chain, protocol):
    """Get APR history for a protocol"""
    days = request.args.get('days', default=30, type=int)
    asset = request.args.get('asset', default=None, type=str)
    
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT 
                    a.symbol,
                    s.apr,
                    s.timestamp
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
            
            query += " ORDER BY s.timestamp ASC"
            
            cur.execute(query, params)
            
            # Group by asset
            data = {}
            for row in cur.fetchall():
                symbol = row[0]
                if symbol not in data:
                    data[symbol] = {'symbol': symbol, 'data': []}
                data[symbol]['data'].append({
                    'timestamp': row[2].isoformat(),
                    'apr': float(row[1])
                })
            
        return jsonify(list(data.values()))
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
