"""Portfolio API routes for fetching user DeFi positions."""

import logging
import os
from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from src.services.portfolio_service import PortfolioService, BLOCKFROST_API_KEY

logger = logging.getLogger(__name__)

portfolio_bp = Blueprint('portfolio', __name__, url_prefix='/api/portfolio')

# Initialize portfolio service
portfolio_service = PortfolioService()


@portfolio_bp.route('/positions', methods=['GET'])
@login_required
def get_positions():
    """
    Get all DeFi positions for the authenticated user.

    Requires wallet authentication (wallet_address must be set).

    Returns:
        JSON with lp_positions, lending_positions, and total_usd_value
    """
    if not current_user.wallet_address:
        return jsonify({
            'error': 'Wallet connection required',
            'message': 'Please connect your Cardano wallet to view your portfolio'
        }), 400

    try:
        positions = portfolio_service.get_all_positions(current_user.wallet_address)

        # Add warning if Blockfrost API key not configured
        if not BLOCKFROST_API_KEY:
            positions['warning'] = 'LP positions require Blockfrost API key. Set BLOCKFROST_API_KEY environment variable. Get a free key at https://blockfrost.io'

        return jsonify(positions)
    except Exception as e:
        logger.error("Error fetching positions for %s: %s",
                    current_user.wallet_address[:20], e)
        return jsonify({
            'error': 'Failed to fetch positions',
            'message': 'Unable to retrieve your DeFi positions. Please try again.'
        }), 500


@portfolio_bp.route('/lp', methods=['GET'])
@login_required
def get_lp_positions():
    """
    Get LP positions from DEXs for the authenticated user.

    Returns positions from Minswap, WingRiders, and SundaeSwap.
    """
    if not current_user.wallet_address:
        return jsonify({
            'error': 'Wallet connection required'
        }), 400

    try:
        positions = portfolio_service.get_lp_positions(current_user.wallet_address)
        return jsonify({
            'lp_positions': [p.to_dict() for p in positions]
        })
    except Exception as e:
        logger.error("Error fetching LP positions: %s", e)
        return jsonify({
            'error': 'Failed to fetch LP positions'
        }), 500


@portfolio_bp.route('/lending', methods=['GET'])
@login_required
def get_lending_positions():
    """
    Get lending positions from Liqwid for the authenticated user.

    Returns supply and borrow positions.
    """
    if not current_user.wallet_address:
        return jsonify({
            'error': 'Wallet connection required'
        }), 400

    try:
        positions = portfolio_service.get_lending_positions(current_user.wallet_address)
        return jsonify({
            'lending_positions': [p.to_dict() for p in positions]
        })
    except Exception as e:
        logger.error("Error fetching lending positions: %s", e)
        return jsonify({
            'error': 'Failed to fetch lending positions'
        }), 500
