"""SundaeSwap protocol adapter for Cardano.

SundaeSwap is a DEX on Cardano, similar to Minswap.
It uses a GraphQL API at https://api.sundae.fi/graphql

API provides:
- Pool data (TVL, reserves, fees)
- Popular pools query (returns top 50)
- Historical ticks data (hourly) for fees/volume
- Protocol-wide stats

HRA (Historic Returns Annualized) is calculated from:
- 24h lpFees (fees returned to LPs) from hourly ticks
- Current TVL
- Formula: (daily_fees / tvl) * 365 * 100
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

import requests

from src.adapters.base import ProtocolAdapter

logger = logging.getLogger(__name__)


# GraphQL query to get popular pools
POOLS_QUERY = """
{
  pools {
    popular {
      id
      version
      assetA {
        ticker
        name
        decimals
      }
      assetB {
        ticker
        name
        decimals
      }
      current {
        tvl {
          quantity
        }
        quantityA {
          quantity
        }
        quantityB {
          quantity
        }
      }
      bidFee
      askFee
    }
  }
}
"""


@dataclass
class SundaePoolMetrics:
    """Container for SundaeSwap pool metrics."""
    pool_id: str
    pair: str
    version: str
    tvl_ada: Optional[Decimal] = None
    tvl_usd: Optional[Decimal] = None
    fee_percent: Optional[Decimal] = None
    reserve_a: Optional[Decimal] = None
    reserve_b: Optional[Decimal] = None
    # HRA (Historic Returns Annualized) from 24h fees
    hra: Optional[Decimal] = None
    fees_24h_usd: Optional[Decimal] = None
    volume_24h_usd: Optional[Decimal] = None


class SundaeSwapAdapter(ProtocolAdapter):
    """Adapter for querying SundaeSwap pool data."""

    def __init__(self, protocol_name: str, config: Dict):
        super().__init__(protocol_name, config)
        self.graphql_url = config.get(
            "graphql_url", "https://api.sundae.fi/graphql"
        )
        self.timeout = config.get("timeout", 30)
        self.max_retries = config.get("max_retries", 3)
        self.min_tvl_ada = config.get("min_tvl_ada", 10000)  # 10K ADA minimum
        self.ada_price_usd = config.get("ada_price_usd", 0.35)  # Default estimate

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "defitracker/1.0",
            "Content-Type": "application/json",
        })

        # Cache for pool data
        self._pool_cache: List[SundaePoolMetrics] = []
        self._cache_timestamp: float = 0
        self._cache_ttl = config.get("cache_ttl", 300)  # 5 minutes

    def get_supported_assets(self) -> List[str]:
        """Return list of pool pair names with TVL above threshold."""
        pools = self._get_pools()
        return [p.pair for p in pools]

    def get_supply_apr(self, asset: str) -> Optional[Decimal]:
        """
        Get the HRA (Historic Returns Annualized) for a pool.
        
        HRA is calculated from actual 24h LP fees divided by TVL, annualized.
        
        Args:
            asset: Pool pair name (e.g., "ADA-NIGHT")
            
        Returns:
            HRA as Decimal percentage, or None if not found
        """
        pools = self._get_pools()
        for pool in pools:
            if pool.pair == asset:
                return pool.hra
        return None

    def get_pool_metrics(self, asset: str) -> Optional[SundaePoolMetrics]:
        """
        Get full pool metrics for a pair.
        
        Args:
            asset: Pool pair name (e.g., "ADA-NIGHT")
            
        Returns:
            SundaePoolMetrics or None if not found
        """
        pools = self._get_pools()
        for pool in pools:
            if pool.pair == asset:
                return pool
        return None

    def get_all_pools(self) -> List[SundaePoolMetrics]:
        """Get all pools meeting the TVL threshold."""
        return self._get_pools()

    def compute_apr_from_onchain(self, asset: str, lookback_days: int = 7) -> Optional[Decimal]:
        """On-chain computation not available for Cardano."""
        logger.info(
            "On-chain APR computation not supported for SundaeSwap (asset=%s)",
            asset,
        )
        return None

    def _get_pools(self) -> List[SundaePoolMetrics]:
        """Fetch and cache pool data from the GraphQL API."""
        now = time.time()
        if now - self._cache_timestamp < self._cache_ttl and self._pool_cache:
            return self._pool_cache

        # Fetch fresh data
        pools = self._fetch_pools()
        if pools:
            self._pool_cache = pools
            self._cache_timestamp = now
        
        return self._pool_cache

    def _fetch_pools(self) -> List[SundaePoolMetrics]:
        """Fetch pools from the GraphQL API."""
        backoff = 2

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(
                    self.graphql_url,
                    json={"query": POOLS_QUERY},
                    timeout=self.timeout
                )

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", backoff))
                    logger.warning(
                        "Rate limited by SundaeSwap API (attempt %s/%s). Sleeping %ss",
                        attempt, self.max_retries, retry_after
                    )
                    time.sleep(retry_after)
                    backoff = min(backoff * 2, 30)
                    continue

                if resp.status_code >= 400:
                    logger.error(
                        "SundaeSwap API error %s: %s",
                        resp.status_code, resp.text[:500]
                    )
                    return []

                data = resp.json()

                if "errors" in data and data["errors"]:
                    logger.error("GraphQL errors: %s", data["errors"])
                    return []

                raw_pools = data.get("data", {}).get("pools", {}).get("popular", [])
                return self._parse_pools(raw_pools)

            except requests.RequestException as exc:
                logger.error(
                    "Error calling SundaeSwap API (attempt %s/%s): %s",
                    attempt, self.max_retries, exc
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

        return []

    def _parse_pools(self, raw_pools: List[Dict]) -> List[SundaePoolMetrics]:
        """Parse raw pool data into SundaePoolMetrics objects."""
        pools = []
        seen_pairs = set()  # Track unique pairs to avoid duplicates

        for p in raw_pools:
            try:
                ticker_a = p.get("assetA", {}).get("ticker", "???")
                ticker_b = p.get("assetB", {}).get("ticker", "???")
                version = p.get("version", "V1")
                
                # Create pair name (version stored separately)
                pair = f"{ticker_a}-{ticker_b}"
                pair_key = f"{pair}-{version}"  # Unique key includes version
                
                # Skip if we've already seen this pair+version
                if pair_key in seen_pairs:
                    continue

                # Parse TVL (in lovelace)
                tvl_lovelace = int(p.get("current", {}).get("tvl", {}).get("quantity", 0))
                tvl_ada = Decimal(tvl_lovelace) / Decimal(1_000_000)
                tvl_usd = tvl_ada * Decimal(str(self.ada_price_usd))

                # Filter by minimum TVL (in ADA)
                if tvl_ada < self.min_tvl_ada:
                    continue

                # Parse fee (comes as [numerator, denominator])
                bid_fee = p.get("bidFee", [0, 1])
                if isinstance(bid_fee, list) and len(bid_fee) == 2:
                    fee_percent = Decimal(bid_fee[0]) / Decimal(bid_fee[1]) * Decimal(100)
                else:
                    fee_percent = Decimal(0)

                # Parse reserves
                qty_a = p.get("current", {}).get("quantityA", {}).get("quantity", 0)
                qty_b = p.get("current", {}).get("quantityB", {}).get("quantity", 0)
                decimals_a = p.get("assetA", {}).get("decimals", 6)
                decimals_b = p.get("assetB", {}).get("decimals", 6)
                
                reserve_a = Decimal(qty_a) / Decimal(10 ** decimals_a) if qty_a else None
                reserve_b = Decimal(qty_b) / Decimal(10 ** decimals_b) if qty_b else None

                pool_metrics = SundaePoolMetrics(
                    pool_id=p.get("id", ""),
                    pair=pair,
                    version=version,
                    tvl_ada=tvl_ada,
                    tvl_usd=tvl_usd,
                    fee_percent=fee_percent,
                    reserve_a=reserve_a,
                    reserve_b=reserve_b,
                )
                pools.append(pool_metrics)
                seen_pairs.add(pair_key)

            except Exception as e:
                logger.warning("Error parsing pool data: %s", e)
                continue

        # Sort by TVL descending
        pools.sort(key=lambda x: x.tvl_usd or Decimal(0), reverse=True)
        
        logger.info("Parsed %d SundaeSwap pools with TVL >= %s ADA", 
                   len(pools), self.min_tvl_ada)
        
        # Fetch 24h fees for HRA calculation
        self._enrich_pools_with_hra(pools)
        
        return pools

    def _enrich_pools_with_hra(self, pools: List[SundaePoolMetrics]) -> None:
        """
        Fetch 24h LP fees from hourly ticks and calculate HRA for each pool.
        
        HRA = (daily_fees_usd / tvl_usd) * 365 * 100
        """
        # Calculate time range for last 24 hours
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(hours=24)
        start_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
        end_str = end_date.strftime('%Y-%m-%d %H:%M:%S')
        
        for pool in pools:
            try:
                fees_24h, volume_24h = self._fetch_24h_fees(
                    pool.pool_id, start_str, end_str
                )
                
                if fees_24h is not None:
                    # Convert lovelace to ADA then to USD
                    fees_ada = Decimal(fees_24h) / Decimal(1_000_000)
                    fees_usd = fees_ada * Decimal(str(self.ada_price_usd))
                    pool.fees_24h_usd = fees_usd
                    
                    # Calculate HRA: (daily_fees / tvl) * 365 * 100
                    if pool.tvl_usd and pool.tvl_usd > 0:
                        pool.hra = (fees_usd / pool.tvl_usd) * Decimal(365) * Decimal(100)
                
                if volume_24h is not None:
                    volume_ada = Decimal(volume_24h) / Decimal(1_000_000)
                    pool.volume_24h_usd = volume_ada * Decimal(str(self.ada_price_usd))
                    
            except Exception as e:
                logger.warning("Error fetching HRA for %s: %s", pool.pair, e)
                continue

    def _fetch_24h_fees(
        self, pool_id: str, start_str: str, end_str: str
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Fetch 24h LP fees and volume for a specific pool from hourly ticks.
        
        Returns:
            Tuple of (total_fees_lovelace, total_volume_lovelace)
        """
        query = """
        {
          pools {
            byId(id: "%s") {
              ticks(interval: Hourly, start: "%s", end: "%s") {
                rich {
                  lpFees(unit: Natural) { quantity }
                  volume(unit: Natural) { quantity }
                }
              }
            }
          }
        }
        """ % (pool_id, start_str, end_str)
        
        try:
            resp = self.session.post(
                self.graphql_url,
                json={"query": query},
                timeout=self.timeout
            )
            
            if resp.status_code != 200:
                return None, None
            
            data = resp.json()
            
            if "errors" in data and data["errors"]:
                # Log but don't fail - some pools may not have ticks data
                logger.debug("Ticks query error for pool %s: %s", 
                           pool_id, data["errors"][0].get("message", ""))
                return None, None
            
            ticks = (data.get("data", {})
                        .get("pools", {})
                        .get("byId", {})
                        .get("ticks", {})
                        .get("rich", []))
            
            if not ticks:
                return None, None
            
            total_fees = sum(
                float(t.get("lpFees", {}).get("quantity", 0) or 0) 
                for t in ticks
            )
            total_volume = sum(
                float(t.get("volume", {}).get("quantity", 0) or 0) 
                for t in ticks
            )
            
            return total_fees, total_volume
            
        except Exception as e:
            logger.debug("Error fetching ticks for pool %s: %s", pool_id, e)
            return None, None

