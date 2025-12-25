"""Database models for APR/APY tracking"""
from datetime import datetime
from typing import Optional
from decimal import Decimal
from dataclasses import dataclass


@dataclass
class APRSnapshot:
    """Represents a single APR snapshot (legacy/generic)"""
    blockchain_id: int
    protocol_id: int
    asset: str
    apr: Decimal
    timestamp: datetime
    snapshot_id: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'snapshot_id': self.snapshot_id,
            'blockchain_id': self.blockchain_id,
            'protocol_id': self.protocol_id,
            'asset': self.asset,
            'apr': float(self.apr),
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class KineticAPYSnapshot:
    """Represents a Kinetic protocol APY snapshot"""
    asset_id: int
    asset_symbol: str  # For convenience, not stored in DB
    
    # Supply side
    supply_apy: Optional[Decimal] = None
    supply_distribution_apy: Optional[Decimal] = None
    total_supply_apy: Optional[Decimal] = None
    
    # Borrow side
    borrow_apy: Optional[Decimal] = None
    borrow_distribution_apy: Optional[Decimal] = None
    
    # Market data
    total_supply_tokens: Optional[Decimal] = None
    total_borrowed_tokens: Optional[Decimal] = None
    utilization_rate: Optional[Decimal] = None
    
    # References
    price_snapshot_id: Optional[int] = None
    timestamp: Optional[datetime] = None
    snapshot_id: Optional[int] = None
    
    # Market type (Primary, ISO: FXRP-USDT0-stXRP, ISO: JOULE-USDC-FLR)
    market_type: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'snapshot_id': self.snapshot_id,
            'asset_id': self.asset_id,
            'asset_symbol': self.asset_symbol,
            'supply_apy': float(self.supply_apy) if self.supply_apy else None,
            'supply_distribution_apy': float(self.supply_distribution_apy) if self.supply_distribution_apy else None,
            'total_supply_apy': float(self.total_supply_apy) if self.total_supply_apy else None,
            'borrow_apy': float(self.borrow_apy) if self.borrow_apy else None,
            'borrow_distribution_apy': float(self.borrow_distribution_apy) if self.borrow_distribution_apy else None,
            'total_supply_tokens': float(self.total_supply_tokens) if self.total_supply_tokens else None,
            'total_borrowed_tokens': float(self.total_borrowed_tokens) if self.total_borrowed_tokens else None,
            'utilization_rate': float(self.utilization_rate) if self.utilization_rate else None,
            'price_snapshot_id': self.price_snapshot_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'market_type': self.market_type
        }


@dataclass
class PriceSnapshot:
    """Represents a token price snapshot"""
    token_symbol: str
    source: str  # e.g., 'blazeswap', 'chainlink'
    
    # Token identification
    token_address: Optional[str] = None
    
    # Price in USD
    price_usd: Optional[Decimal] = None
    
    # Price in another token
    quote_token_symbol: Optional[str] = None
    quote_token_address: Optional[str] = None
    price_in_quote: Optional[Decimal] = None
    
    # Source details
    pair_address: Optional[str] = None
    reserve_token: Optional[Decimal] = None
    reserve_quote: Optional[Decimal] = None
    
    # Timestamps
    timestamp: Optional[datetime] = None
    snapshot_id: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'snapshot_id': self.snapshot_id,
            'token_symbol': self.token_symbol,
            'token_address': self.token_address,
            'price_usd': float(self.price_usd) if self.price_usd else None,
            'quote_token_symbol': self.quote_token_symbol,
            'quote_token_address': self.quote_token_address,
            'price_in_quote': float(self.price_in_quote) if self.price_in_quote else None,
            'source': self.source,
            'pair_address': self.pair_address,
            'reserve_token': float(self.reserve_token) if self.reserve_token else None,
            'reserve_quote': float(self.reserve_quote) if self.reserve_quote else None,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
