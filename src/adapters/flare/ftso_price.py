"""FTSO v2 (Flare Time Series Oracle) Price Feed Adapter

Fetches token prices directly from Flare's native decentralized oracle system.
Uses FtsoV2 contract (not the deprecated v1 feeds).

Much simpler and more reliable than DEX-based price queries.

Reference: https://dev.flare.network/
"""

import logging
from decimal import Decimal
from typing import Dict, Optional
from web3 import Web3
from web3.middleware import geth_poa_middleware

logger = logging.getLogger(__name__)

# FtsoV2 contract address (from Flare Contract Registry)
FTSO_V2_ADDRESS = '0x7BDE3Df0624114eDB3A67dFe6753e62f4e7c1d20'

# Feed indices for common tokens (discovered from getFeedId)
# Format: symbol -> (index, feed_id_symbol)
FTSO_V2_FEEDS = {
    'FLR': (0, 'FLR/USD'),
    'WFLR': (0, 'FLR/USD'),  # WFLR uses same feed as FLR
    'SGB': (1, 'SGB/USD'),
    'BTC': (2, 'BTC/USD'),
    'XRP': (3, 'XRP/USD'),
    'FXRP': (3, 'XRP/USD'),  # FXRP uses XRP price
    'STXRP': (3, 'XRP/USD'),  # stXRP uses XRP price
    'LTC': (4, 'LTC/USD'),
    'XLM': (5, 'XLM/USD'),
    'DOGE': (6, 'DOGE/USD'),
    'ADA': (7, 'ADA/USD'),
    'ALGO': (8, 'ALGO/USD'),
    'ETH': (9, 'ETH/USD'),
    'WETH': (9, 'ETH/USD'),  # WETH uses same feed as ETH
    'FLRETH': (9, 'ETH/USD'),  # FLRETH uses ETH price
    'FIL': (10, 'FIL/USD'),
    'ARB': (11, 'ARB/USD'),
    'AVAX': (12, 'AVAX/USD'),
    'BNB': (13, 'BNB/USD'),
    'POL': (14, 'POL/USD'),
    'SOL': (15, 'SOL/USD'),
    'USDC': (16, 'USDC/USD'),
    'USDT': (17, 'USDT/USD'),
    'USDT0': (17, 'USDT/USD'),  # USDT0 uses USDT price
    'XDC': (18, 'XDC/USD'),
    'TRX': (19, 'TRX/USD'),
    'LINK': (20, 'LINK/USD'),
    'ATOM': (21, 'ATOM/USD'),
    'DOT': (22, 'DOT/USD'),
    'TON': (23, 'TON/USD'),
    'ICP': (24, 'ICP/USD'),
    'SHIB': (25, 'SHIB/USD'),
    'USDS': (26, 'USDS/USD'),
    'BCH': (27, 'BCH/USD'),
    'NEAR': (28, 'NEAR/USD'),
    'LEO': (29, 'LEO/USD'),
    'SFLR': (0, 'FLR/USD'),  # SFLR is staked FLR, uses FLR price as base
}

# FtsoV2 ABI - minimal interface for price queries
FTSO_V2_ABI = [
    {
        "inputs": [{"name": "_index", "type": "uint256"}],
        "name": "getFeedByIndex",
        "outputs": [
            {"name": "_value", "type": "uint256"},
            {"name": "_decimals", "type": "int8"},
            {"name": "_timestamp", "type": "uint64"}
        ],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"name": "_index", "type": "uint256"}],
        "name": "getFeedId",
        "outputs": [{"name": "", "type": "bytes21"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "_feedId", "type": "bytes21"}],
        "name": "getFeedById",
        "outputs": [
            {"name": "_value", "type": "uint256"},
            {"name": "_decimals", "type": "int8"},
            {"name": "_timestamp", "type": "uint64"}
        ],
        "stateMutability": "payable",
        "type": "function"
    }
]


class FTSOPriceFeed:
    """Fetch prices from Flare's native FtsoV2 oracle system."""
    
    def __init__(self, web3: Web3, inject_poa_middleware: bool = False):
        """
        Initialize FTSO v2 price feed.
        
        Args:
            web3: Web3 instance connected to Flare network
            inject_poa_middleware: Whether to inject POA middleware (needed for some setups)
        """
        self.web3 = web3
        
        if inject_poa_middleware:
            try:
                web3.middleware_onion.inject(geth_poa_middleware, layer=0)
            except ValueError:
                pass  # Already injected
        
        self._contract = web3.eth.contract(
            address=Web3.to_checksum_address(FTSO_V2_ADDRESS),
            abi=FTSO_V2_ABI
        )
        self._price_cache: Dict[str, tuple] = {}  # symbol -> (price, timestamp)
        
    def get_price_usd(self, symbol: str) -> Optional[Decimal]:
        """
        Get current USD price for a token from FtsoV2.
        
        Args:
            symbol: Token symbol (FLR, ETH, USDT, etc.)
            
        Returns:
            Price in USD as Decimal, or None if unavailable
        """
        symbol_upper = symbol.upper()
        
        if symbol_upper not in FTSO_V2_FEEDS:
            logger.warning(f"No FtsoV2 feed configured for {symbol}")
            return None
            
        feed_index, feed_name = FTSO_V2_FEEDS[symbol_upper]
        
        try:
            value, decimals, timestamp = self._contract.functions.getFeedByIndex(feed_index).call()
            
            # Calculate price with proper decimal handling
            if decimals >= 0:
                price_decimal = Decimal(value) / Decimal(10 ** decimals)
            else:
                price_decimal = Decimal(value) * Decimal(10 ** abs(decimals))
            
            logger.debug(f"FTSO {symbol} ({feed_name}): ${price_decimal:.6f} USD")
            return price_decimal
            
        except Exception as e:
            logger.error(f"Error fetching FtsoV2 price for {symbol}: {e}")
            return None
    
    def get_flr_price_usd(self) -> Optional[Decimal]:
        """
        Convenience method to get FLR price in USD.
        
        Returns:
            FLR price in USD, or None if unavailable
        """
        return self.get_price_usd('FLR')
    
    def get_available_feeds(self) -> list:
        """Return list of available feed symbols."""
        return list(FTSO_V2_FEEDS.keys())
    
    def get_multiple_prices(self, symbols: list) -> Dict[str, Optional[Decimal]]:
        """
        Get prices for multiple symbols.
        
        Args:
            symbols: List of token symbols
            
        Returns:
            Dict mapping symbol -> price (or None if unavailable)
        """
        return {sym: self.get_price_usd(sym) for sym in symbols}


def get_ftso_flr_price(web3: Web3) -> Optional[Decimal]:
    """
    Simple helper function to get FLR price from FtsoV2.
    
    Args:
        web3: Web3 instance connected to Flare
        
    Returns:
        FLR price in USD, or None if unavailable
    """
    feed = FTSOPriceFeed(web3)
    return feed.get_flr_price_usd()


def get_ftso_price(web3: Web3, symbol: str) -> Optional[Decimal]:
    """
    Simple helper function to get any token price from FtsoV2.
    
    Args:
        web3: Web3 instance connected to Flare
        symbol: Token symbol (FLR, ETH, XRP, etc.)
        
    Returns:
        Token price in USD, or None if unavailable
    """
    feed = FTSOPriceFeed(web3)
    return feed.get_price_usd(symbol)
