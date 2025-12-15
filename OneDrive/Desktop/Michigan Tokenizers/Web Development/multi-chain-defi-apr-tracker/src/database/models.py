"""Database models for APR tracking"""
from datetime import datetime
from typing import Optional
from decimal import Decimal


class APRSnapshot:
    """Represents a single APR snapshot"""
    
    def __init__(
        self,
        blockchain_id: int,
        protocol_id: int,
        asset: str,
        apr: Decimal,
        timestamp: datetime,
        snapshot_id: Optional[int] = None
    ):
        self.snapshot_id = snapshot_id
        self.blockchain_id = blockchain_id
        self.protocol_id = protocol_id
        self.asset = asset
        self.apr = apr
        self.timestamp = timestamp
    
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
