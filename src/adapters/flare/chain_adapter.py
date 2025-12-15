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
        # from src.adapters.flare.blazeswap import BlazeSwapAdapter
        
        if 'kinetic' in self.config.get('protocols', {}):
            kinetic_config = self.config['protocols']['kinetic']
            if kinetic_config.get('enabled', False):
                kinetic_adapter = KineticAdapter('kinetic', kinetic_config)
                # Set Web3 instance for on-chain queries
                kinetic_adapter.set_web3_instance(self.get_web3_instance())
                self.protocols['kinetic'] = kinetic_adapter
    
    def get_web3_instance(self):
        """Get web3.py instance for Flare"""
        if self.web3_instance is None:
            if not self.rpc_url:
                raise ValueError("RPC URL not configured for Flare")
            self.web3_instance = Web3(Web3.HTTPProvider(self.rpc_url))
        return self.web3_instance
