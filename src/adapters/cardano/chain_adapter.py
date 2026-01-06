"""Cardano chain adapter implementation."""

import logging
from typing import Dict

from src.adapters.base import ChainAdapter
from src.adapters.cardano.minswap import MinswapAdapter
from src.adapters.cardano.liqwid import LiqwidAdapter
from src.adapters.cardano.sundaeswap import SundaeSwapAdapter
from src.adapters.cardano.wingriders import WingRidersAdapter
from src.adapters.cardano.muesliswap import MuesliSwapAdapter

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

        if "sundaeswap" in protocols_cfg:
            sundae_cfg = protocols_cfg["sundaeswap"]
            if sundae_cfg.get("enabled", False):
                self.protocols["sundaeswap"] = SundaeSwapAdapter("sundaeswap", sundae_cfg)
                logger.info("Initialized SundaeSwap adapter for Cardano")

        if "wingriders" in protocols_cfg:
            wingriders_cfg = protocols_cfg["wingriders"]
            if wingriders_cfg.get("enabled", False):
                self.protocols["wingriders"] = WingRidersAdapter("wingriders", wingriders_cfg)
                logger.info("Initialized WingRiders adapter for Cardano")

        if "muesliswap" in protocols_cfg:
            muesliswap_cfg = protocols_cfg["muesliswap"]
            if muesliswap_cfg.get("enabled", False):
                self.protocols["muesliswap"] = MuesliSwapAdapter("muesliswap", muesliswap_cfg)
                logger.info("Initialized MuesliSwap adapter for Cardano")

    def get_web3_instance(self):
        """
        Cardano does not use web3; keep signature for compatibility.

        Returns:
            None
        """
        return None

