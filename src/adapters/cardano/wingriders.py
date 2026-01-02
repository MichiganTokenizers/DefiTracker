"""WingRiders protocol adapter for Cardano.

WingRiders is a DEX on Cardano with embedded staking rewards.
It uses a GraphQL API at https://api.mainnet.wingriders.com/graphql

API provides:
- Pool data (TVL, reserves, fees)
- feesAPR: Trading fee APR (similar to HRA on other DEXs)
- stakingAPR: Additional yield from embedded ADA staking
- Token metadata for display names

Note: WingRiders provides APR directly from the API, no calculation needed.
Total APR = feesAPR + stakingAPR
"""

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

import requests

from src.adapters.base import ProtocolAdapter

logger = logging.getLogger(__name__)


# GraphQL query to get pools with metadata
POOLS_QUERY = """
{
  liquidityPoolsWithMetadata {
    pools {
      ... on LiquidityPoolV1 {
        version
        poolType
        tokenA { policyId assetName quantity }
        tokenB { policyId assetName quantity }
        tvlInAda
        feesAPR
        stakingAPR(timeframe: CURRENT_EPOCH)
      }
      ... on LiquidityPoolV2 {
        version
        poolType
        tokenA { policyId assetName quantity }
        tokenB { policyId assetName quantity }
        tvlInAda
        feesAPR
        stakingAPR(timeframe: CURRENT_EPOCH)
      }
    }
    metadata {
      asset { policyId assetName }
      ticker
      name
    }
  }
}
"""


@dataclass
class WingRidersPoolMetrics:
    """Container for WingRiders pool metrics."""
    pair: str
    version: str
    pool_type: str
    tvl_ada: Optional[Decimal] = None
    tvl_usd: Optional[Decimal] = None
    fees_apr: Optional[Decimal] = None  # Trading fee APR
    staking_apr: Optional[Decimal] = None  # Embedded staking APR
    total_apr: Optional[Decimal] = None  # fees_apr + staking_apr
    reserve_a: Optional[Decimal] = None
    reserve_b: Optional[Decimal] = None
    ticker_a: str = ""
    ticker_b: str = ""


class WingRidersAdapter(ProtocolAdapter):
    """Adapter for querying WingRiders pool data."""

    def __init__(self, protocol_name: str, config: Dict):
        super().__init__(protocol_name, config)
        self.graphql_url = config.get(
            "graphql_url", "https://api.mainnet.wingriders.com/graphql"
        )
        self.timeout = config.get("timeout", 30)
        self.max_retries = config.get("max_retries", 3)
        self.min_tvl_usd = config.get("min_tvl_usd", 10000)
        self.ada_price_usd = config.get("ada_price_usd", 0.35)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "defitracker/1.0",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip, deflate, br",
        })

        # Cache for pool data
        self._pool_cache: List[WingRidersPoolMetrics] = []
        self._cache_timestamp: float = 0
        self._cache_ttl = config.get("cache_ttl", 300)

    def get_supported_assets(self) -> List[str]:
        """Return list of pool pair names with TVL above threshold."""
        pools = self._get_pools()
        return [p.pair for p in pools]

    def get_supply_apr(self, asset: str) -> Optional[Decimal]:
        """
        Get the total APR (fees + staking) for a pool.
        
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

    def get_pool_metrics(self, asset: str) -> Optional[WingRidersPoolMetrics]:
        """
        Get full pool metrics for a pair.
        
        Args:
            asset: Pool pair name (e.g., "ADA-NIGHT")
            
        Returns:
            WingRidersPoolMetrics or None if not found
        """
        pools = self._get_pools()
        for pool in pools:
            if pool.pair == asset:
                return pool
        return None

    def get_all_pools(self) -> List[WingRidersPoolMetrics]:
        """Get all pools meeting the TVL threshold."""
        return self._get_pools()

    def compute_apr_from_onchain(self, asset: str, lookback_days: int = 7) -> Optional[Decimal]:
        """On-chain computation not needed - API provides APR directly."""
        logger.info(
            "On-chain APR computation not needed for WingRiders - using API data (asset=%s)",
            asset,
        )
        return self.get_supply_apr(asset)

    def _get_pools(self) -> List[WingRidersPoolMetrics]:
        """Fetch and cache pool data from the GraphQL API."""
        now = time.time()
        if now - self._cache_timestamp < self._cache_ttl and self._pool_cache:
            return self._pool_cache

        pools = self._fetch_pools()
        if pools:
            self._pool_cache = pools
            self._cache_timestamp = now
        
        return self._pool_cache

    def _fetch_pools(self) -> List[WingRidersPoolMetrics]:
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
                        "Rate limited by WingRiders API (attempt %s/%s). Sleeping %ss",
                        attempt, self.max_retries, retry_after
                    )
                    time.sleep(retry_after)
                    backoff = min(backoff * 2, 30)
                    continue

                if resp.status_code >= 400:
                    logger.error(
                        "WingRiders API error %s: %s",
                        resp.status_code, resp.text[:500]
                    )
                    return []

                data = resp.json()

                if "errors" in data and data["errors"]:
                    logger.error("GraphQL errors: %s", data["errors"])
                    return []

                result = data.get("data", {}).get("liquidityPoolsWithMetadata", {})
                raw_pools = result.get("pools", [])
                metadata = result.get("metadata", [])
                
                return self._parse_pools(raw_pools, metadata)

            except requests.RequestException as exc:
                logger.error(
                    "Error calling WingRiders API (attempt %s/%s): %s",
                    attempt, self.max_retries, exc
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

        return []

    def _parse_pools(
        self, raw_pools: List[Dict], metadata: List[Dict]
    ) -> List[WingRidersPoolMetrics]:
        """Parse raw pool data into WingRidersPoolMetrics objects."""
        # Build ticker lookup from metadata
        ticker_map = self._build_ticker_map(metadata)
        
        pools = []
        seen_pairs = set()

        for p in raw_pools:
            if not p:
                continue
                
            try:
                # Skip pools without TVL data
                if not p.get("tvlInAda"):
                    continue
                    
                # Get token info
                token_a = p.get("tokenA", {})
                token_b = p.get("tokenB", {})
                
                ticker_a = self._get_ticker(token_a, ticker_map)
                ticker_b = self._get_ticker(token_b, ticker_map)
                
                version = p.get("version", "V1")
                pool_type = p.get("poolType", "CONSTANT_PRODUCT")
                
                # Create unique pair key including version
                pair = f"{ticker_a}-{ticker_b}"
                pair_key = f"{pair}-{version}"
                
                # Skip if we've already seen this pair+version
                if pair_key in seen_pairs:
                    continue

                # Parse TVL (in lovelace - divide by 1M to get ADA)
                tvl_lovelace = float(p.get("tvlInAda", 0))
                tvl_ada = Decimal(str(tvl_lovelace)) / Decimal(1_000_000)
                tvl_usd = tvl_ada * Decimal(str(self.ada_price_usd))

                # Filter by minimum TVL
                if tvl_usd < self.min_tvl_usd:
                    continue

                # Parse APRs (already in percentage form)
                fees_apr = Decimal(str(p.get("feesAPR") or 0))
                staking_apr = Decimal(str(p.get("stakingAPR") or 0))
                total_apr = fees_apr + staking_apr

                # Parse reserves
                reserve_a = Decimal(token_a.get("quantity", 0)) if token_a.get("quantity") else None
                reserve_b = Decimal(token_b.get("quantity", 0)) if token_b.get("quantity") else None

                pool_metrics = WingRidersPoolMetrics(
                    pair=pair,
                    version=version,
                    pool_type=pool_type,
                    tvl_ada=tvl_ada,
                    tvl_usd=tvl_usd,
                    fees_apr=fees_apr,
                    staking_apr=staking_apr,
                    total_apr=total_apr,
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
        
        logger.info("Parsed %d WingRiders pools with TVL >= $%s", 
                   len(pools), self.min_tvl_usd)
        return pools

    def _build_ticker_map(self, metadata: List[Dict]) -> Dict[str, str]:
        """Build a mapping from asset key to ticker name."""
        ticker_map = {"_": "ADA"}  # ADA has empty policyId
        
        for m in metadata:
            asset = m.get("asset", {})
            policy_id = asset.get("policyId", "")
            asset_name = asset.get("assetName", "")
            key = f"{policy_id}_{asset_name}"
            
            ticker = m.get("ticker") or m.get("name")
            if ticker:
                ticker_map[key] = ticker
                
        return ticker_map

    def _get_ticker(self, token: Dict, ticker_map: Dict[str, str]) -> str:
        """Get ticker symbol for a token."""
        policy_id = token.get("policyId", "")
        asset_name = token.get("assetName", "")
        
        # ADA has empty policyId
        if not policy_id:
            return "ADA"
            
        key = f"{policy_id}_{asset_name}"
        
        if key in ticker_map:
            return ticker_map[key]
        
        # Try to decode asset name as hex
        try:
            decoded = bytes.fromhex(asset_name).decode("utf-8", errors="ignore")
            if decoded:
                return decoded
        except Exception:
            pass
            
        return "???"

