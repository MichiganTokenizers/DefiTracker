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
        # TODO: Import and initialize protocol adapters
        # from src.adapters.flare.kinetic import KineticAdapter
        # from src.adapters.flare.blazeswap import BlazeSwapAdapter
        # 
        # if 'kinetic' in self.config.get('protocols', {}):
        #     self.protocols['kinetic'] = KineticAdapter(
        #         'kinetic', 
        #         self.config['protocols']['kinetic']
        #     )
        pass
    
    def get_web3_instance(self):
        """Get web3.py instance for Flare"""
        if self.web3_instance is None:
            if not self.rpc_url:
                raise ValueError("RPC URL not configured for Flare")
            self.web3_instance = Web3(Web3.HTTPProvider(self.rpc_url))
        return self.web3_instance
