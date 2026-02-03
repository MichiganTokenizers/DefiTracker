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

Farming Rewards:
- Fetched from https://api.yield.sundaeswap.finance/graphql
- SUNDAE token rewards distributed daily to eligible pools
- Farming APR = (daily_sundae_emission * sundae_price / tvl) * 365 * 100
- SUNDAE price derived from ADA-SUNDAE pool reserves

Total APR = HRA (trading fees) + Farming APR (SUNDAE rewards)
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

# GraphQL query fragment for pool fields
POOL_FIELDS = """
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
"""

# Farming API URL (separate from main API)
FARMING_API_URL = "https://api.yield.sundaeswap.finance/graphql"

# GraphQL query to get yield farming programs
FARMING_PROGRAMS_QUERY = """
{
  programs {
    id
    type
    label
    emittedAsset
    dailyEmission {
      assetID
      amount
    }
    eligiblePools {
      poolIdent
      lpAsset
      assetA
      assetB
    }
    status
    poolEmissions
  }
}
"""

# SUNDAE token asset ID (policy_id.asset_name)
SUNDAE_ASSET_ID = "9a9693a9a37912a5097918f97918d15240c92ab729a0b7c4aa144d77.53554e444145"


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
    # Original tickers from API (before pair name normalization)
    ticker_a: str = ""  # First token ticker (as in pair name, left side)
    ticker_b: str = ""  # Second token ticker (as in pair name, right side)
    # HRA (Historic Returns Annualized) from 24h fees
    hra: Optional[Decimal] = None
    fees_24h_usd: Optional[Decimal] = None
    volume_24h_usd: Optional[Decimal] = None
    # Farming rewards (SUNDAE token emissions)
    farming_apr: Optional[Decimal] = None  # APR from SUNDAE farming rewards
    daily_sundae_emission: Optional[Decimal] = None  # Daily SUNDAE tokens for this pool
    has_farm: bool = False  # Whether pool has active farming rewards
    # Total APR = HRA (fees) + farming_apr (rewards)
    total_apr: Optional[Decimal] = None


class SundaeSwapAdapter(ProtocolAdapter):
    """Adapter for querying SundaeSwap pool data."""

    def __init__(self, protocol_name: str, config: Dict):
        super().__init__(protocol_name, config)
        self.graphql_url = config.get(
            "graphql_url", "https://api.sundae.fi/graphql"
        )
        self.farming_url = config.get(
            "farming_url", FARMING_API_URL
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
        
        # Cache for SUNDAE token price (in ADA)
        self._sundae_price_ada: Optional[Decimal] = None
        self._sundae_price_timestamp: float = 0

    def get_supported_assets(self) -> List[str]:
        """Return list of pool pair names with TVL above threshold."""
        pools = self._get_pools()
        return [p.pair for p in pools]

    def get_supply_apr(self, asset: str) -> Optional[Decimal]:
        """
        Get the total APR (trading fees + farming rewards) for a pool.
        
        Total APR includes:
        - HRA (Historic Returns Annualized) from 24h trading fees
        - Farming APR from SUNDAE token rewards (if pool is eligible)
        
        Args:
            asset: Pool pair name (e.g., "ADA-NIGHT")
            
        Returns:
            Total APR as Decimal percentage, or None if not found
        """
        pools = self._get_pools()
        for pool in pools:
            if pool.pair == asset:
                return pool.total_apr
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

    def get_all_pools(self, tracked_pool_ids: Optional[List[str]] = None) -> List[SundaePoolMetrics]:
        """Get all pools meeting the TVL threshold plus any tracked pools.

        Args:
            tracked_pool_ids: Optional list of pool IDs to always include,
                              regardless of whether they're in the popular list
                              or meet TVL threshold.

        Returns:
            List of SundaePoolMetrics for all qualifying pools.
        """
        return self._get_pools(tracked_pool_ids=tracked_pool_ids)

    def compute_apr_from_onchain(self, asset: str, lookback_days: int = 7) -> Optional[Decimal]:
        """On-chain computation not available for Cardano."""
        logger.info(
            "On-chain APR computation not supported for SundaeSwap (asset=%s)",
            asset,
        )
        return None

    def _get_pools(self, tracked_pool_ids: Optional[List[str]] = None) -> List[SundaePoolMetrics]:
        """Fetch and cache pool data from the GraphQL API.

        Args:
            tracked_pool_ids: Optional list of pool IDs to always include.
        """
        now = time.time()

        # Note: We don't use cache when tracked_pool_ids is provided
        # because we need to merge in the tracked pools fresh each time
        if tracked_pool_ids is None:
            if now - self._cache_timestamp < self._cache_ttl and self._pool_cache:
                return self._pool_cache

        # Fetch fresh data from popular pools
        pools = self._fetch_pools()

        # Fetch any tracked pools that weren't in the popular list
        if tracked_pool_ids:
            existing_ids = {p.pool_id for p in pools}
            missing_ids = [pid for pid in tracked_pool_ids if pid not in existing_ids]

            if missing_ids:
                logger.info("Fetching %d tracked pools not in popular list", len(missing_ids))
                tracked_pools = self._fetch_pools_by_ids(missing_ids)
                pools.extend(tracked_pools)

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
                return self._parse_pools(raw_pools, apply_tvl_filter=True)

            except requests.RequestException as exc:
                logger.error(
                    "Error calling SundaeSwap API (attempt %s/%s): %s",
                    attempt, self.max_retries, exc
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

        return []

    def _fetch_pools_by_ids(self, pool_ids: List[str]) -> List[SundaePoolMetrics]:
        """Fetch specific pools by their IDs.

        Uses the pools.byIds GraphQL query to fetch pools that may not
        be in the popular list. These pools are returned regardless of
        TVL threshold since they're explicitly tracked.

        Args:
            pool_ids: List of pool IDs to fetch

        Returns:
            List of SundaePoolMetrics for the requested pools
        """
        if not pool_ids:
            return []

        # Build the query with pool IDs as a JSON array
        import json
        ids_json = json.dumps(pool_ids)
        query = f"""
        {{
          pools {{
            byIds(ids: {ids_json}) {{
              {POOL_FIELDS}
            }}
          }}
        }}
        """

        backoff = 2
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(
                    self.graphql_url,
                    json={"query": query},
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
                    logger.error("GraphQL errors fetching pools by ID: %s", data["errors"])
                    return []

                raw_pools = data.get("data", {}).get("pools", {}).get("byIds", [])
                # Don't apply TVL filter for tracked pools
                pools = self._parse_pools(raw_pools, apply_tvl_filter=False)
                logger.info("Fetched %d tracked pools by ID", len(pools))
                return pools

            except requests.RequestException as exc:
                logger.error(
                    "Error fetching pools by ID (attempt %s/%s): %s",
                    attempt, self.max_retries, exc
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

        return []

    def search_pools(self, term: str) -> List[SundaePoolMetrics]:
        """Search for pools by term (e.g., token ticker).

        Useful for discovering pools that aren't in the popular list.

        Args:
            term: Search term (e.g., "iUSD")

        Returns:
            List of matching SundaePoolMetrics
        """
        query = f"""
        {{
          pools {{
            search(term: "{term}") {{
              {POOL_FIELDS}
            }}
          }}
        }}
        """

        try:
            resp = self.session.post(
                self.graphql_url,
                json={"query": query},
                timeout=self.timeout
            )

            if resp.status_code != 200:
                logger.warning("Search query failed: %s", resp.status_code)
                return []

            data = resp.json()

            if "errors" in data and data["errors"]:
                logger.warning("Search query errors: %s", data["errors"])
                return []

            raw_pools = data.get("data", {}).get("pools", {}).get("search", [])
            # Don't apply TVL filter for search results
            return self._parse_pools(raw_pools, apply_tvl_filter=False)

        except Exception as e:
            logger.warning("Error searching pools: %s", e)
            return []

    def _parse_pools(self, raw_pools: List[Dict], apply_tvl_filter: bool = True) -> List[SundaePoolMetrics]:
        """Parse raw pool data into SundaePoolMetrics objects."""
        pools = []
        seen_pairs = set()  # Track unique pairs to avoid duplicates

        for p in raw_pools:
            try:
                orig_ticker_a = p.get("assetA", {}).get("ticker", "???")
                orig_ticker_b = p.get("assetB", {}).get("ticker", "???")
                version = p.get("version", "V1")
                
                # Parse reserves first (before potential swap)
                qty_a = p.get("current", {}).get("quantityA", {}).get("quantity", 0)
                qty_b = p.get("current", {}).get("quantityB", {}).get("quantity", 0)
                decimals_a = p.get("assetA", {}).get("decimals", 6)
                decimals_b = p.get("assetB", {}).get("decimals", 6)
                
                reserve_a = Decimal(qty_a) / Decimal(10 ** decimals_a) if qty_a else None
                reserve_b = Decimal(qty_b) / Decimal(10 ** decimals_b) if qty_b else None
                
                # Ensure ADA is always SECOND in the pair name (TOKEN-ADA format)
                # For stablecoin pairs, use alphabetical order
                # This matches the Minswap convention
                ticker_a = orig_ticker_a
                ticker_b = orig_ticker_b
                if orig_ticker_a == 'ADA' and orig_ticker_b != 'ADA':
                    # Swap so ADA is second in pair name
                    ticker_a, ticker_b = orig_ticker_b, orig_ticker_a
                    # Also swap reserves to match new order
                    reserve_a, reserve_b = reserve_b, reserve_a
                
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

                # Filter by minimum TVL (in ADA) unless explicitly disabled
                if apply_tvl_filter and tvl_ada < self.min_tvl_ada:
                    continue

                # Parse fee (comes as [numerator, denominator])
                bid_fee = p.get("bidFee", [0, 1])
                if isinstance(bid_fee, list) and len(bid_fee) == 2:
                    fee_percent = Decimal(bid_fee[0]) / Decimal(bid_fee[1]) * Decimal(100)
                else:
                    fee_percent = Decimal(0)

                pool_metrics = SundaePoolMetrics(
                    pool_id=p.get("id", ""),
                    pair=pair,
                    version=version,
                    tvl_ada=tvl_ada,
                    tvl_usd=tvl_usd,
                    fee_percent=fee_percent,
                    reserve_a=reserve_a,
                    reserve_b=reserve_b,
                    ticker_a=ticker_a,
                    ticker_b=ticker_b,
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
        
        # Fetch farming rewards for eligible pools
        self._enrich_pools_with_farming(pools)
        
        # Calculate total APR for all pools
        for pool in pools:
            pool.total_apr = (pool.hra or Decimal(0)) + (pool.farming_apr or Decimal(0))
        
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

    def _enrich_pools_with_farming(self, pools: List[SundaePoolMetrics]) -> None:
        """
        Fetch farming rewards from the yield farming API and calculate farming APR.
        
        Farming APR = (daily_sundae_emission * sundae_price / tvl) * 365 * 100
        
        Uses the SUNDAE yield farming program which distributes SUNDAE tokens
        daily to eligible liquidity pools based on their share of total liquidity.
        """
        try:
            # Fetch farming programs
            farming_data = self._fetch_farming_programs()
            if not farming_data:
                logger.debug("No farming program data available")
                return
            
            # Get SUNDAE price in ADA
            sundae_price = self._get_sundae_price(pools)
            if not sundae_price or sundae_price <= 0:
                logger.warning("Could not get SUNDAE price for farming APR calculation")
                return
            
            # Build mapping from pool ID to daily SUNDAE emission
            pool_emissions = farming_data.get("pool_emissions", {})
            
            if not pool_emissions:
                logger.debug("No pool emissions data in farming program")
                return
            
            # SUNDAE token has 6 decimals
            sundae_decimals = Decimal(1_000_000)
            
            farms_found = 0
            for pool in pools:
                # Pool IDs in farming API may be truncated or different format
                # Try matching by prefix
                emission_amount = None
                
                for farm_pool_id, amount in pool_emissions.items():
                    # Match if pool ID starts with the farming pool ID or vice versa
                    if (pool.pool_id.startswith(farm_pool_id) or 
                        farm_pool_id.startswith(pool.pool_id)):
                        emission_amount = amount
                        break
                
                if emission_amount is not None and emission_amount > 0:
                    # Convert raw emission to SUNDAE tokens
                    daily_sundae = Decimal(emission_amount) / sundae_decimals
                    pool.daily_sundae_emission = daily_sundae
                    pool.has_farm = True
                    
                    # Calculate farming APR
                    if pool.tvl_ada and pool.tvl_ada > 0:
                        # Daily reward value in ADA
                        daily_reward_ada = daily_sundae * sundae_price
                        
                        # Farming APR = (daily_reward / tvl) * 365 * 100
                        pool.farming_apr = (
                            daily_reward_ada / pool.tvl_ada
                        ) * Decimal(365) * Decimal(100)
                        
                        farms_found += 1
                        
                        logger.debug(
                            "Pool %s farming: %.0f SUNDAE/day, price=%.6f ADA, "
                            "tvl=%.0f ADA, farming_apr=%.2f%%",
                            pool.pair, daily_sundae, sundae_price,
                            pool.tvl_ada, pool.farming_apr
                        )
            
            logger.info(
                "Enriched %d pools with SUNDAE farming rewards (SUNDAE price: %.6f ADA)",
                farms_found, sundae_price
            )
            
        except Exception as e:
            logger.warning("Error enriching pools with farming data: %s", e)

    def _fetch_farming_programs(self) -> Optional[Dict]:
        """
        Fetch yield farming programs from the farming API.
        
        Returns:
            Dict with 'pool_emissions' mapping pool IDs to daily SUNDAE amounts,
            or None if fetch fails.
        """
        try:
            resp = self.session.post(
                self.farming_url,
                json={"query": FARMING_PROGRAMS_QUERY},
                timeout=self.timeout
            )
            
            if resp.status_code != 200:
                logger.warning(
                    "Farming API returned status %s", resp.status_code
                )
                return None
            
            data = resp.json()
            
            if "errors" in data and data["errors"]:
                logger.warning("Farming API errors: %s", data["errors"][:200])
                return None
            
            programs = data.get("data", {}).get("programs", [])
            
            # Find the SUNDAE farming program
            for prog in programs:
                if prog.get("id") == "SUNDAE" and prog.get("type") == "yield":
                    pool_emissions = prog.get("poolEmissions") or {}
                    
                    logger.debug(
                        "Found SUNDAE farming program with %d pool emissions",
                        len(pool_emissions)
                    )
                    
                    return {
                        "program_id": prog.get("id"),
                        "label": prog.get("label"),
                        "pool_emissions": pool_emissions,
                        "daily_emission": prog.get("dailyEmission", []),
                    }
            
            logger.debug("SUNDAE farming program not found in %d programs", len(programs))
            return None
            
        except Exception as e:
            logger.warning("Error fetching farming programs: %s", e)
            return None

    def _get_sundae_price(self, pools: List[SundaePoolMetrics]) -> Optional[Decimal]:
        """
        Get the SUNDAE token price in ADA from the ADA-SUNDAE pool reserves.
        
        Uses the highest TVL ADA-SUNDAE pool (typically V3) for most accurate price.
        
        Args:
            pools: List of pool metrics (used to find ADA-SUNDAE pool)
            
        Returns:
            SUNDAE price in ADA, or None if not available.
        """
        now = time.time()
        
        # Return cached price if still valid
        if (self._sundae_price_ada is not None and 
            now - self._sundae_price_timestamp < self._cache_ttl):
            return self._sundae_price_ada
        
        # Find ADA-SUNDAE pool with highest TVL
        sundae_pool = None
        for pool in pools:
            if pool.pair in ["SUNDAE-ADA", "ADA-SUNDAE"]:
                if sundae_pool is None or (pool.tvl_ada or 0) > (sundae_pool.tvl_ada or 0):
                    sundae_pool = pool
        
        if sundae_pool and sundae_pool.reserve_a and sundae_pool.reserve_b:
            # Use ticker_a and ticker_b to determine which reserve is which
            # Price = ADA_reserve / SUNDAE_reserve
            if sundae_pool.ticker_a == "SUNDAE":
                # reserve_a is SUNDAE, reserve_b is ADA
                if sundae_pool.reserve_a > 0:
                    self._sundae_price_ada = sundae_pool.reserve_b / sundae_pool.reserve_a
            else:
                # reserve_a is ADA, reserve_b is SUNDAE
                if sundae_pool.reserve_b > 0:
                    self._sundae_price_ada = sundae_pool.reserve_a / sundae_pool.reserve_b
            
            self._sundae_price_timestamp = now
            
            logger.debug(
                "SUNDAE price from %s pool: %.6f ADA",
                sundae_pool.version, self._sundae_price_ada
            )
            return self._sundae_price_ada
        
        # Fallback: Query the API directly for ADA-SUNDAE pools
        try:
            query = """
            {
              pools {
                popular {
                  id
                  version
                  assetA { ticker decimals }
                  assetB { ticker decimals }
                  current {
                    quantityA { quantity }
                    quantityB { quantity }
                    tvl { quantity }
                  }
                }
              }
            }
            """
            
            resp = self.session.post(
                self.graphql_url,
                json={"query": query},
                timeout=self.timeout
            )
            
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            all_pools = data.get("data", {}).get("pools", {}).get("popular", [])
            
            # Find highest TVL ADA-SUNDAE pool
            best_pool = None
            best_tvl = 0
            
            for p in all_pools:
                ticker_a = p.get("assetA", {}).get("ticker", "")
                ticker_b = p.get("assetB", {}).get("ticker", "")
                
                if set([ticker_a, ticker_b]) == {"ADA", "SUNDAE"}:
                    tvl = int(p.get("current", {}).get("tvl", {}).get("quantity", 0))
                    if tvl > best_tvl:
                        best_tvl = tvl
                        best_pool = p
            
            if best_pool:
                ticker_a = best_pool.get("assetA", {}).get("ticker", "")
                decimals_a = best_pool.get("assetA", {}).get("decimals", 6)
                decimals_b = best_pool.get("assetB", {}).get("decimals", 6)
                
                qty_a = int(best_pool.get("current", {}).get("quantityA", {}).get("quantity", 0))
                qty_b = int(best_pool.get("current", {}).get("quantityB", {}).get("quantity", 0))
                
                reserve_a = Decimal(qty_a) / Decimal(10 ** decimals_a)
                reserve_b = Decimal(qty_b) / Decimal(10 ** decimals_b)
                
                if ticker_a == "SUNDAE" and reserve_a > 0:
                    self._sundae_price_ada = reserve_b / reserve_a
                elif ticker_a == "ADA" and reserve_b > 0:
                    self._sundae_price_ada = reserve_a / reserve_b
                
                self._sundae_price_timestamp = now
                
                logger.debug(
                    "SUNDAE price from API: %.6f ADA (from %s pool)",
                    self._sundae_price_ada, best_pool.get("version")
                )
                return self._sundae_price_ada
                
        except Exception as e:
            logger.debug("Error fetching SUNDAE price from API: %s", e)
        
        return None

