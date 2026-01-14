"""Flare chain adapter implementation"""
from typing import Dict
from web3 import Web3
from src.adapters.base import ChainAdapter, ProtocolAdapter


class FlareChainAdapter(ChainAdapter):
    """Adapter for Flare blockchain"""
    
    def __init__(self, config: Dict):
        super().__init__("flare", config)
        self.web3_instance = None
        self.initialize_protocols()
    
    def initialize_protocols(self):
        """Initialize Flare protocol adapters"""
        from src.adapters.flare.kinetic import KineticAdapter
        from src.adapters.flare.enosys import EnosysAdapter
        # from src.adapters.flare.blazeswap import BlazeSwapAdapter
        
        protocols_config = self.config.get('protocols', {})
        
        # Initialize Kinetic (lending protocol)
        if 'kinetic' in protocols_config:
            kinetic_config = protocols_config['kinetic']
            if kinetic_config.get('enabled', False):
                # Pass parent config so Kinetic can access BlazeSwap config
                kinetic_config['_parent_config'] = protocols_config
                kinetic_adapter = KineticAdapter('kinetic', kinetic_config)
                # Set Web3 instance for on-chain queries
                kinetic_adapter.set_web3_instance(self.get_web3_instance())
                self.protocols['kinetic'] = kinetic_adapter
        
        # Initialize Enosys DEX V3 (concentrated liquidity DEX)
        if 'enosys' in protocols_config:
            enosys_config = protocols_config['enosys']
            if enosys_config.get('enabled', False):
                enosys_adapter = EnosysAdapter('enosys', enosys_config)
                enosys_adapter.set_web3_instance(self.get_web3_instance())
                self.protocols['enosys'] = enosys_adapter
    
    def get_web3_instance(self):
        """Get web3.py instance for Flare"""
        if self.web3_instance is None:
            if not self.rpc_url:
                raise ValueError("RPC URL not configured for Flare")
            self.web3_instance = Web3(Web3.HTTPProvider(self.rpc_url))
        return self.web3_instance
