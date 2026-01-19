"""Chain registry for managing multiple chains"""
import yaml
from typing import Dict, List, Optional
from pathlib import Path
from src.adapters.base import ChainAdapter
from src.adapters.cardano.chain_adapter import CardanoChainAdapter


class ChainRegistry:
    """Registry for managing multiple blockchain adapters"""
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "chains.yaml"
        self.config_path = Path(config_path)
        self.chains: Dict[str, ChainAdapter] = {}
        self.load_config()
    
    def load_config(self):
        """Load chain configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Chain config not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.chain_configs = config.get('chains', {})
    
    def get_chain(self, chain_name: str) -> Optional[ChainAdapter]:
        """Get a chain adapter by name"""
        if chain_name not in self.chains:
            self._initialize_chain(chain_name)
        return self.chains.get(chain_name)
    
    def _initialize_chain(self, chain_name: str):
        """Initialize a chain adapter"""
        chain_config = self.chain_configs.get(chain_name)
        if not chain_config:
            raise ValueError(f"Chain '{chain_name}' not found in config")
        
        if not chain_config.get('enabled', False):
            return None
        
        # Map chain names to adapter classes
        chain_adapters = {
            'cardano': CardanoChainAdapter,
            # Add more chains here as they're implemented
        }
        
        adapter_class = chain_adapters.get(chain_name)
        if not adapter_class:
            raise ValueError(f"No adapter available for chain '{chain_name}'")
        
        self.chains[chain_name] = adapter_class(chain_config)
    
    def get_all_active_chains(self) -> List[str]:
        """Get list of all enabled chain names"""
        return [
            name for name, config in self.chain_configs.items()
            if config.get('enabled', False)
        ]
    
    def collect_all_aprs(self) -> Dict[str, Dict[str, Dict[str, Optional[float]]]]:
        """
        Collect APR data from all active chains.
        
        Returns:
            Dict mapping chain_name -> protocol_name -> asset -> APR
        """
        results = {}
        
        for chain_name in self.get_all_active_chains():
            chain_adapter = self.get_chain(chain_name)
            if chain_adapter:
                try:
                    chain_results = chain_adapter.collect_aprs()
                    # Convert Decimal to float for JSON serialization
                    results[chain_name] = {
                        protocol: {
                            asset: float(apr) if apr is not None else None
                            for asset, apr in assets.items()
                        }
                        for protocol, assets in chain_results.items()
                    }
                except Exception as e:
                    print(f"Error collecting APRs for {chain_name}: {e}")
                    results[chain_name] = {}
        
        return results
