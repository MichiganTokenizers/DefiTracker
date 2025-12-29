"""Cardano chain adapter implementation."""

import logging
from typing import Dict

from src.adapters.base import ChainAdapter
from src.adapters.cardano.minswap import MinswapAdapter
from src.adapters.cardano.liqwid import LiqwidAdapter

logger = logging.getLogger(__name__)


class CardanoChainAdapter(ChainAdapter):
    """Adapter for Cardano blockchain."""

    def __init__(self, config: Dict):
        super().__init__("cardano", config)
        self.initialize_protocols()

    def initialize_protocols(self):
        """Initialize Cardano protocol adapters."""
        protocols_cfg = self.config.get("protocols", {})

        if "minswap" in protocols_cfg:
            minswap_cfg = protocols_cfg["minswap"]
            if minswap_cfg.get("enabled", False):
                self.protocols["minswap"] = MinswapAdapter("minswap", minswap_cfg)
                logger.info("Initialized Minswap adapter for Cardano")

        if "liqwid" in protocols_cfg:
            liqwid_cfg = protocols_cfg["liqwid"]
            if liqwid_cfg.get("enabled", False):
                self.protocols["liqwid"] = LiqwidAdapter("liqwid", liqwid_cfg)
                logger.info("Initialized Liqwid adapter for Cardano")

    def get_web3_instance(self):
        """
        Cardano does not use web3; keep signature for compatibility.

        Returns:
            None
        """
        return None

