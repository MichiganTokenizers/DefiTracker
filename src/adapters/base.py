"""Base abstract classes for chain and protocol adapters"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from decimal import Decimal


class ProtocolAdapter(ABC):
    """Base class for protocol-specific adapters"""
    
    def __init__(self, protocol_name: str, config: Dict):
        self.protocol_name = protocol_name
        self.config = config
    
    @abstractmethod
    def get_supply_apr(self, asset: str) -> Optional[Decimal]:
        """
        Get supply APR for a specific asset.
        
        Args:
            asset: Token symbol or address
            
        Returns:
            APR as Decimal (e.g., 0.05 for 5%), or None if unavailable
        """
        pass
    
    @abstractmethod
    def get_supported_assets(self) -> List[str]:
        """
        Get list of assets supported by this protocol.
        
        Returns:
            List of asset symbols or addresses
        """
        pass
    
    @abstractmethod
    def compute_apr_from_onchain(
        self, 
        asset: str, 
        lookback_days: int = 7
    ) -> Optional[Decimal]:
        """
        Compute APR from on-chain data as fallback.
        
        Args:
            asset: Token symbol or address
            lookback_days: Number of days to look back for data
            
        Returns:
            APR as Decimal, or None if computation fails
        """
        pass


class ChainAdapter(ABC):
    """Base class for chain-specific adapters"""
    
    def __init__(self, chain_name: str, config: Dict):
        self.chain_name = chain_name
        self.config = config
        self.rpc_url = config.get('rpc_url')
        self.protocols: Dict[str, ProtocolAdapter] = {}
    
    @abstractmethod
    def initialize_protocols(self):
        """Initialize protocol adapters for this chain"""
        pass
    
    @abstractmethod
    def get_web3_instance(self):
        """Get web3.py instance for this chain"""
        pass
    
    def get_protocol(self, protocol_name: str) -> Optional[ProtocolAdapter]:
        """Get a protocol adapter by name"""
        return self.protocols.get(protocol_name)
    
    def get_all_protocols(self) -> Dict[str, ProtocolAdapter]:
        """Get all protocol adapters for this chain"""
        return self.protocols
    
    def collect_aprs(self) -> Dict[str, Dict[str, Optional[Decimal]]]:
        """
        Collect APR data from all protocols on this chain.
        
        Returns:
            Dict mapping protocol_name -> asset -> APR
        """
        results = {}
        
        for protocol_name, protocol_adapter in self.protocols.items():
            protocol_results = {}
            assets = protocol_adapter.get_supported_assets()
            
            for asset in assets:
                # Try API first, fallback to on-chain computation
                apr = protocol_adapter.get_supply_apr(asset)
                if apr is None:
                    apr = protocol_adapter.compute_apr_from_onchain(asset)
                protocol_results[asset] = apr
            
            results[protocol_name] = protocol_results
        
        return results
