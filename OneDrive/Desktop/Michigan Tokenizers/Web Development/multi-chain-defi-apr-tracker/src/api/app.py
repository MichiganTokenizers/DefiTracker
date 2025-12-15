"""Flask API application"""
from flask import Flask, jsonify
from flask_cors import CORS
from src.collectors.chain_registry import ChainRegistry

app = Flask(__name__)
CORS(app)

# Initialize chain registry
chain_registry = ChainRegistry()


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200


@app.route('/chains', methods=['GET'])
def get_chains():
    """Get list of all active chains"""
    chains = chain_registry.get_all_active_chains()
    return jsonify({'chains': chains}), 200


@app.route('/aprs', methods=['GET'])
def get_aprs():
    """Get current APR data from all chains"""
    chain = chain_registry.get_chain('flare')  # TODO: Support querying specific chain
    if not chain:
        return jsonify({'error': 'Chain not found or disabled'}), 404
    
    aprs = chain.collect_aprs()
    return jsonify(aprs), 200


@app.route('/aprs/<chain_name>', methods=['GET'])
def get_chain_aprs(chain_name: str):
    """Get APR data for a specific chain"""
    chain = chain_registry.get_chain(chain_name)
    if not chain:
        return jsonify({'error': 'Chain not found or disabled'}), 404
    
    aprs = chain.collect_aprs()
    return jsonify(aprs), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
