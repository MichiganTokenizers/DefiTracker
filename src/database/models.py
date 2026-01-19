"""Database models for APR/APY tracking"""
from datetime import datetime
from typing import Optional, Literal
from decimal import Decimal
from dataclasses import dataclass

# Valid yield types
YieldType = Literal['lp', 'supply', 'borrow']


@dataclass
class APRSnapshot:
    """Represents a single APR snapshot (legacy/generic)"""
    blockchain_id: int
    protocol_id: int
    asset: str
    apr: Decimal
    timestamp: datetime
    snapshot_id: Optional[int] = None
    yield_type: Optional[str] = 'lp'  # lp, supply, or borrow
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'snapshot_id': self.snapshot_id,
            'blockchain_id': self.blockchain_id,
            'protocol_id': self.protocol_id,
            'asset': self.asset,
            'apr': float(self.apr),
            'timestamp': self.timestamp.isoformat(),
            'yield_type': self.yield_type
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


@dataclass
class LiqwidAPYSnapshot:
    """Represents a Liqwid Finance protocol APY snapshot"""
    asset_id: int
    asset_symbol: str  # For convenience, not stored in DB
    
    # Market identification
    market_id: Optional[str] = None
    
    # Supply side APY (what lenders earn)
    supply_apy: Optional[Decimal] = None  # Base supply APY
    lq_supply_apy: Optional[Decimal] = None  # LQ token reward APY
    total_supply_apy: Optional[Decimal] = None  # Base + LQ rewards
    
    # Borrow side APY (what borrowers pay)
    borrow_apy: Optional[Decimal] = None
    
    # Market state data
    total_supply: Optional[Decimal] = None
    total_borrows: Optional[Decimal] = None
    utilization_rate: Optional[Decimal] = None
    available_liquidity: Optional[Decimal] = None
    
    # Yield type (supply or borrow)
    yield_type: Optional[str] = 'supply'
    
    # Timestamps
    timestamp: Optional[datetime] = None
    snapshot_id: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'snapshot_id': self.snapshot_id,
            'asset_id': self.asset_id,
            'asset_symbol': self.asset_symbol,
            'market_id': self.market_id,
            'supply_apy': float(self.supply_apy) if self.supply_apy else None,
            'lq_supply_apy': float(self.lq_supply_apy) if self.lq_supply_apy else None,
            'total_supply_apy': float(self.total_supply_apy) if self.total_supply_apy else None,
            'borrow_apy': float(self.borrow_apy) if self.borrow_apy else None,
            'total_supply': float(self.total_supply) if self.total_supply else None,
            'total_borrows': float(self.total_borrows) if self.total_borrows else None,
            'utilization_rate': float(self.utilization_rate) if self.utilization_rate else None,
            'available_liquidity': float(self.available_liquidity) if self.available_liquidity else None,
            'yield_type': self.yield_type,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
