"""Shared price service using Pyth Network Hermes API."""

import logging
import time
from decimal import Decimal
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class PriceService:
    """Fetches live token prices from Pyth Network's Hermes REST API.

    Primary use: ADA/USD price for converting ADA-denominated values to USD
    across all DEX adapters.

    Prices are cached with a configurable TTL (default 5 minutes).
    Falls back to a configured default if the API is unreachable.
    """

    HERMES_BASE_URL = "https://hermes.pyth.network"

    # ADA/USD price feed ID on Pyth
    ADA_USD_FEED_ID = "2a01deaec9e51a579277b34b122399984d0bbf57e2458a7e42fecd2829867a0d"

    def __init__(self, default_ada_price: Decimal = Decimal("0.35"), cache_ttl: int = 300):
        self._default_ada_price = default_ada_price
        self._cache_ttl = cache_ttl

        self._ada_price: Optional[Decimal] = None
        self._ada_price_timestamp: float = 0

        self._fallback_fn = None

        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "defitracker/1.0"})

    def set_fallback(self, fallback_fn):
        """Register a fallback function that returns Optional[Decimal] ADA/USD price."""
        self._fallback_fn = fallback_fn

    def get_ada_price(self) -> Decimal:
        """Get the current ADA/USD price.

        Tries in order:
        1. Cached price if within TTL
        2. Pyth Hermes API
        3. Fallback function (e.g. Minswap pool-derived)
        4. Stale cached price
        5. Configured default
        """
        now = time.time()

        if self._ada_price is not None and (now - self._ada_price_timestamp) < self._cache_ttl:
            return self._ada_price

        price = self._fetch_from_pyth()
        if price is not None:
            self._ada_price = price
            self._ada_price_timestamp = now
            logger.info("ADA/USD price from Pyth: $%.6f", price)
            return price

        if self._fallback_fn is not None:
            try:
                fallback_price = self._fallback_fn()
                if fallback_price is not None and fallback_price > 0:
                    self._ada_price = fallback_price
                    self._ada_price_timestamp = now
                    logger.info("ADA/USD price from fallback: $%.6f", fallback_price)
                    return fallback_price
            except Exception as e:
                logger.warning("Fallback price fetch failed: %s", e)

        if self._ada_price is not None:
            logger.warning("Using stale ADA/USD price: $%.6f", self._ada_price)
            return self._ada_price

        logger.warning("Using default ADA/USD price: $%.6f", self._default_ada_price)
        return self._default_ada_price

    def _fetch_from_pyth(self) -> Optional[Decimal]:
        """Fetch ADA/USD price from Pyth Hermes REST API."""
        try:
            resp = self._session.get(
                f"{self.HERMES_BASE_URL}/v2/updates/price/latest",
                params={"ids[]": f"0x{self.ADA_USD_FEED_ID}"},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning("Pyth Hermes API returned status %s", resp.status_code)
                return None

            data = resp.json()
            parsed = data.get("parsed", [])
            if not parsed:
                logger.warning("No parsed data in Pyth response")
                return None

            price_data = parsed[0].get("price", {})
            raw_price = price_data.get("price")
            expo = price_data.get("expo")

            if raw_price is None or expo is None:
                logger.warning("Missing price or expo in Pyth response")
                return None

            price = Decimal(str(raw_price)) * Decimal(10) ** Decimal(str(expo))

            if price <= 0:
                logger.warning("Invalid ADA/USD price from Pyth: %s", price)
                return None

            return price

        except requests.RequestException as e:
            logger.warning("Pyth Hermes API request failed: %s", e)
            return None
        except (KeyError, IndexError, ValueError) as e:
            logger.warning("Error parsing Pyth response: %s", e)
            return None
