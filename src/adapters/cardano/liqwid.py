"""Liqwid Finance protocol adapter for Cardano.

Liqwid is a lending/borrowing protocol on Cardano, similar to Kinetic on Flare.
It uses a GraphQL API to expose market data including supply/borrow rates.

API Documentation: https://docs.liqwid.finance/
GraphQL Endpoint: https://v2.api.liqwid.finance/graphql
"""

import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional

import requests

from src.adapters.base import ProtocolAdapter

logger = logging.getLogger(__name__)


# GraphQL query to get all markets with their current rates
# The API structure is: liqwid.data.markets.results[]
MARKETS_QUERY = """
query GetMarkets {
  liqwid {
    data {
      markets {
        results {
          id
          displayName
          symbol
          supply
          borrow
          liquidity
          supplyAPY
          borrowAPY
          lqSupplyAPY
          utilization
          asset {
            name
            decimals
          }
        }
      }
    }
  }
}
"""

# Query for a specific market by ID
MARKET_BY_ID_QUERY = """
query GetMarket($marketId: String!) {
  liqwid {
    data {
      market(id: $marketId) {
        id
        displayName
        symbol
        supply
        borrow
        liquidity
        supplyAPY
        borrowAPY
        lqSupplyAPY
        utilization
        asset {
          name
          decimals
        }
      }
    }
  }
}
"""


class LiqwidAdapter(ProtocolAdapter):
    """Adapter for Liqwid Finance lending protocol on Cardano.
    
    Liqwid allows users to supply assets to earn interest or borrow
    assets by providing collateral. The protocol exposes supply and
    borrow APYs for each market through their GraphQL API.
    """

    def __init__(self, protocol_name: str, config: Dict):
        super().__init__(protocol_name, config)
        self.graphql_url = config.get(
            "graphql_url", "https://v2.api.liqwid.finance/graphql"
        )
        self.timeout = config.get("timeout", 15)
        self.max_retries = config.get("max_retries", 3)
        
        # Markets to track (by asset symbol like ADA, DJED, iUSD, etc.)
        self.tracked_markets = config.get("markets", [])
        
        # Cache for market data
        self._market_cache: Dict[str, Dict] = {}
        self._cache_timestamp: float = 0
        self._cache_ttl = config.get("cache_ttl", 60)  # Cache for 60 seconds
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "defitracker/1.0",
            "Content-Type": "application/json",
        })

    # ------------------------------------------------------------------ #
    # ProtocolAdapter interface
    # ------------------------------------------------------------------ #

    def get_supported_assets(self) -> List[str]:
        """Return the list of tracked market asset symbols."""
        if self.tracked_markets:
            return [m.get("symbol", m.get("asset_id", "")) for m in self.tracked_markets]
        
        # If no markets configured, try to fetch all available markets
        markets = self._fetch_all_markets()
        if markets:
            return [self._get_market_symbol(m) for m in markets]
        return []

    def get_supply_apr(self, asset: str) -> Optional[Decimal]:
        """
        Get supply APY for a specific market/asset.
        
        Note: Liqwid returns APY (not APR), so we pass it through directly.
        The naming convention in the base class uses APR, but for lending
        protocols that compound, APY is the appropriate metric.
        
        This returns the total supply APY including LQ rewards.

        Args:
            asset: Asset symbol (e.g., ADA, DJED, iUSD)

        Returns:
            Supply APY as Decimal (percentage, e.g., 5.25 for 5.25%)
        """
        market = self._get_market_data(asset)
        if not market:
            logger.warning("Market data not found for asset %s", asset)
            return None

        supply_apy = market.get("supplyAPY")
        lq_supply_apy = market.get("lqSupplyAPY", 0)
        
        if supply_apy is None:
            logger.warning("Supply APY not found in market data for %s", asset)
            return None

        try:
            # API returns APY as a decimal (e.g., 0.0525 for 5.25%)
            # Convert to percentage and add LQ rewards
            base_apy = Decimal(str(supply_apy)) * Decimal("100")
            lq_apy = Decimal(str(lq_supply_apy)) * Decimal("100") if lq_supply_apy else Decimal("0")
            return base_apy + lq_apy
        except Exception as e:
            logger.error("Could not convert supply APY %s for %s: %s", supply_apy, asset, e)
            return None

    def get_borrow_apr(self, asset: str) -> Optional[Decimal]:
        """
        Get borrow APY for a specific market/asset.

        Args:
            asset: Asset symbol (e.g., ADA, DJED, iUSD)

        Returns:
            Borrow APY as Decimal (percentage)
        """
        market = self._get_market_data(asset)
        if not market:
            logger.warning("Market data not found for asset %s", asset)
            return None

        borrow_apy = market.get("borrowAPY")
        
        if borrow_apy is None:
            logger.warning("Borrow APY not found in market data for %s", asset)
            return None

        try:
            # Convert to percentage
            return Decimal(str(borrow_apy)) * Decimal("100")
        except Exception as e:
            logger.error("Could not convert borrow APY %s for %s: %s", borrow_apy, asset, e)
            return None

    def get_market_state(self, asset: str) -> Optional[Dict]:
        """
        Get full market state including supply, borrows, utilization, etc.
        
        Args:
            asset: Asset symbol
            
        Returns:
            Dict with market state data, or None if unavailable
        """
        market = self._get_market_data(asset)
        if not market:
            return None
        
        asset_info = market.get("asset", {})
        
        try:
            decimals = asset_info.get("decimals", 6)
            
            # Liqwid API v2 returns APY as decimals (e.g., 0.023697 for 2.37%)
            # Convert to percentage
            supply_apy_raw = market.get("supplyAPY")
            borrow_apy_raw = market.get("borrowAPY")
            lq_supply_apy_raw = market.get("lqSupplyAPY", 0)
            
            supply_apy = self._to_decimal(supply_apy_raw) * Decimal("100") if supply_apy_raw else Decimal("0")
            borrow_apy = self._to_decimal(borrow_apy_raw) * Decimal("100") if borrow_apy_raw else Decimal("0")
            lq_supply_apy = self._to_decimal(lq_supply_apy_raw) * Decimal("100") if lq_supply_apy_raw else Decimal("0")
            
            # Total supply APY includes LQ rewards
            total_supply_apy = supply_apy + lq_supply_apy
            
            return {
                "market_id": market.get("id"),
                "asset_symbol": self._get_market_symbol(market),
                "asset_name": market.get("displayName"),
                "decimals": decimals,
                "total_supply": self._to_decimal(market.get("supply")),
                "total_borrows": self._to_decimal(market.get("borrow")),
                "utilization": self._to_decimal(market.get("utilization")),
                "supply_apy": supply_apy,
                "borrow_apy": borrow_apy,
                "lq_supply_apy": lq_supply_apy,  # LQ token rewards APY
                "total_supply_apy": total_supply_apy,  # Base + LQ rewards
                "available_liquidity": self._to_decimal(market.get("liquidity")),
            }
        except Exception as e:
            logger.error("Error parsing market state for %s: %s", asset, e)
            return None

    def compute_apr_from_onchain(self, asset: str, lookback_days: int = 7) -> Optional[Decimal]:
        """
        Compute APR from historical on-chain data.
        
        Cardano doesn't have the same RPC query model as EVM chains,
        so this would require indexer data. For now, we rely on the API.
        """
        logger.info(
            "On-chain APR computation not implemented for Liqwid (asset=%s, lookback=%s)",
            asset,
            lookback_days,
        )
        return None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _to_decimal(self, value) -> Optional[Decimal]:
        """Safely convert a value to Decimal."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    def _get_market_symbol(self, market: Dict) -> str:
        """Extract asset symbol from market data."""
        # For Liqwid API v2, the symbol is directly on the market object
        if market.get("symbol"):
            return market["symbol"]
        if market.get("displayName"):
            return market["displayName"]
        if market.get("id"):
            return market["id"]
        
        return "unknown"

    def _get_market_data(self, asset: str) -> Optional[Dict]:
        """
        Get market data for an asset, using cache if available.
        
        Args:
            asset: Asset symbol (e.g., ADA, DJED)
            
        Returns:
            Market data dict or None
        """
        # Check cache
        now = time.time()
        if now - self._cache_timestamp < self._cache_ttl and asset.upper() in self._market_cache:
            return self._market_cache[asset.upper()]
        
        # Refresh cache
        markets = self._fetch_all_markets()
        if not markets:
            return None
        
        # Update cache
        self._market_cache = {}
        for market in markets:
            symbol = self._get_market_symbol(market).upper()
            self._market_cache[symbol] = market
        self._cache_timestamp = now
        
        return self._market_cache.get(asset.upper())

    def _fetch_all_markets(self) -> Optional[List[Dict]]:
        """Fetch all markets from the GraphQL API."""
        payload = {
            "query": MARKETS_QUERY,
            "variables": {}
        }
        
        response = self._graphql_request(payload)
        if response and "data" in response:
            # Navigate the nested structure: liqwid.data.markets.results
            liqwid_data = response["data"].get("liqwid", {})
            data = liqwid_data.get("data", {})
            markets_obj = data.get("markets", {})
            markets = markets_obj.get("results", [])
            logger.debug("Fetched %d markets from Liqwid API", len(markets))
            return markets
        
        return None

    def _graphql_request(self, payload: Dict) -> Optional[Dict]:
        """Execute a GraphQL request with retry logic."""
        backoff = 2
        
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(
                    self.graphql_url,
                    json=payload,
                    timeout=self.timeout
                )
                
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", backoff))
                    logger.warning(
                        "Rate limited by Liqwid API (attempt %s/%s). Sleeping %ss",
                        attempt,
                        self.max_retries,
                        retry_after,
                    )
                    time.sleep(retry_after)
                    backoff = min(backoff * 2, 30)
                    continue
                
                if resp.status_code >= 400:
                    logger.error(
                        "Liqwid API error %s: %s",
                        resp.status_code,
                        resp.text[:500],
                    )
                    return None
                
                result = resp.json()
                
                # Check for GraphQL errors
                if "errors" in result and result["errors"]:
                    logger.error("GraphQL errors: %s", result["errors"])
                    return None
                
                return result
                
            except requests.RequestException as exc:
                logger.error(
                    "Error calling Liqwid API (attempt %s/%s): %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
        
        return None

