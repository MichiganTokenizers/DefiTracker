"""WingRiders protocol adapter for Cardano.

WingRiders is a DEX on Cardano with embedded staking rewards and farming.
It uses a GraphQL API at https://api.mainnet.wingriders.com/graphql

API provides:
- Pool data (TVL, reserves, fees)
- feesAPR: Trading fee APR (similar to HRA on other DEXs)
- stakingAPR: Additional yield from embedded ADA staking
- Farm yield APR: Additional rewards for farming LP tokens
- Boosting APR: Additional rewards for WRT token boosting
- Token metadata for display names

Total APR = feesAPR + stakingAPR + farmAPR + boostingAPR
"""

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

import requests

from src.adapters.base import ProtocolAdapter

logger = logging.getLogger(__name__)


# GraphQL query to get pools with metadata and market data (volume, fees)
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
        marketData {
          volumeA24h
          volumeB24h
          feeA24h
          feeB24h
        }
      }
      ... on LiquidityPoolV2 {
        version
        poolType
        tokenA { policyId assetName quantity }
        tokenB { policyId assetName quantity }
        tvlInAda
        feesAPR
        stakingAPR(timeframe: CURRENT_EPOCH)
        swapFeeInBasis
        feeBasis
        marketData {
          volumeA24h
          volumeB24h
          feeA24h
          feeB24h
        }
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

# GraphQL query to get active farms with yield APRs
FARMS_QUERY = """
{
  activeFarms {
    poolId
    isDoubleYield
    yieldAPR(timeframe: CURRENT_EPOCH) {
      regular { apr }
      boosting { apr }
    }
    liquidityPool {
      ... on LiquidityPoolV1 {
        version
        tokenA { policyId assetName }
        tokenB { policyId assetName }
      }
      ... on LiquidityPoolV2 {
        version
        tokenA { policyId assetName }
        tokenB { policyId assetName }
      }
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
    farm_apr: Optional[Decimal] = None  # Farm yield APR (regular rewards)
    boosting_apr: Optional[Decimal] = None  # Boosting APR (WRT token boost)
    total_apr: Optional[Decimal] = None  # Sum of all APR components
    reserve_a: Optional[Decimal] = None
    reserve_b: Optional[Decimal] = None
    ticker_a: str = ""
    ticker_b: str = ""
    has_farm: bool = False  # Whether pool has active farm
    swap_fee_percent: Optional[Decimal] = None  # Swap fee percentage (e.g., 0.30 for 0.30%)
    volume_24h_usd: Optional[Decimal] = None  # 24h trading volume in USD
    fees_24h_usd: Optional[Decimal] = None  # 24h trading fees in USD


class WingRidersAdapter(ProtocolAdapter):
    """Adapter for querying WingRiders pool data."""

    def __init__(self, protocol_name: str, config: Dict):
        super().__init__(protocol_name, config)
        self.graphql_url = config.get(
            "graphql_url", "https://api.mainnet.wingriders.com/graphql"
        )
        self.timeout = config.get("timeout", 30)
        self.max_retries = config.get("max_retries", 3)
        self.min_tvl_ada = config.get("min_tvl_ada", 10000)  # 10K ADA minimum
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
        """Fetch pools and farms from the GraphQL API."""
        backoff = 2

        for attempt in range(1, self.max_retries + 1):
            try:
                # Fetch pools
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
                
                # Fetch active farms for additional APRs
                farms_data = self._fetch_farms()
                
                return self._parse_pools(raw_pools, metadata, farms_data)

            except requests.RequestException as exc:
                logger.error(
                    "Error calling WingRiders API (attempt %s/%s): %s",
                    attempt, self.max_retries, exc
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

        return []

    def _fetch_farms(self) -> Dict[str, Dict]:
        """Fetch active farms and return mapping of pool pair to farm APRs."""
        try:
            resp = self.session.post(
                self.graphql_url,
                json={"query": FARMS_QUERY},
                timeout=self.timeout
            )
            
            if resp.status_code != 200:
                logger.warning("Failed to fetch farms: %s", resp.status_code)
                return {}
            
            data = resp.json()
            
            if "errors" in data and data["errors"]:
                logger.warning("Farms query errors: %s", data["errors"][:200])
                return {}
            
            farms = data.get("data", {}).get("activeFarms", [])
            
            # Build mapping from pair+version to farm APRs
            farm_map = {}
            for farm in farms:
                pool = farm.get("liquidityPool")
                if not pool:
                    continue
                
                token_a = pool.get("tokenA", {})
                token_b = pool.get("tokenB", {})
                version = pool.get("version", "V1")
                
                # Build key from token identifiers
                key_a = f"{token_a.get('policyId', '')}_{token_a.get('assetName', '')}"
                key_b = f"{token_b.get('policyId', '')}_{token_b.get('assetName', '')}"
                pool_key = f"{key_a}|{key_b}|{version}"
                
                yield_apr = farm.get("yieldAPR") or {}
                regular = yield_apr.get("regular") or {}
                boosting = yield_apr.get("boosting") or {}
                
                farm_map[pool_key] = {
                    "farm_apr": regular.get("apr") or 0,
                    "boosting_apr": boosting.get("apr") or 0,
                }
            
            logger.info("Fetched %d active farms with yield programs", len(farm_map))
            return farm_map
            
        except Exception as e:
            logger.warning("Error fetching farms: %s", e)
            return {}

    def _parse_pools(
        self, raw_pools: List[Dict], metadata: List[Dict], farms_data: Dict[str, Dict]
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
                
                # Ensure ADA is always SECOND in the pair name (TOKEN-ADA format)
                # For stablecoin pairs, use alphabetical order
                # This matches the Minswap/MuesliSwap convention
                if ticker_a == 'ADA' and ticker_b != 'ADA':
                    # Swap so ADA is second
                    ticker_a, ticker_b = ticker_b, ticker_a
                    token_a, token_b = token_b, token_a
                
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

                # Filter by minimum TVL (in ADA)
                if tvl_ada < self.min_tvl_ada:
                    continue

                # Parse base APRs (already in percentage form)
                fees_apr = Decimal(str(p.get("feesAPR") or 0))
                staking_apr = Decimal(str(p.get("stakingAPR") or 0))
                
                # Look up farm APRs using token identifiers
                key_a = f"{token_a.get('policyId', '')}_{token_a.get('assetName', '')}"
                key_b = f"{token_b.get('policyId', '')}_{token_b.get('assetName', '')}"
                farm_key = f"{key_a}|{key_b}|{version}"
                
                farm_info = farms_data.get(farm_key, {})
                farm_apr = Decimal(str(farm_info.get("farm_apr", 0)))
                boosting_apr = Decimal(str(farm_info.get("boosting_apr", 0)))
                has_farm = bool(farm_info)
                
                # Total APR = fees + staking + farm + boosting
                total_apr = fees_apr + staking_apr + farm_apr + boosting_apr
                
                # Parse swap fee (V2 pools have swapFeeInBasis/feeBasis, V1 use default 0.3%)
                swap_fee_percent = None
                swap_fee_basis = p.get("swapFeeInBasis")
                fee_basis = p.get("feeBasis")
                if swap_fee_basis is not None and fee_basis is not None and fee_basis > 0:
                    # Convert basis points to percentage (e.g., 30/10000 = 0.003 -> 0.30%)
                    swap_fee_percent = Decimal(str(swap_fee_basis)) / Decimal(str(fee_basis)) * Decimal(100)
                elif version == "V1":
                    # V1 pools have a fixed 0.3% swap fee
                    swap_fee_percent = Decimal("0.30")

                # Parse reserves
                reserve_a = Decimal(token_a.get("quantity", 0)) if token_a.get("quantity") else None
                reserve_b = Decimal(token_b.get("quantity", 0)) if token_b.get("quantity") else None
                
                # Parse 24h volume and fees from marketData
                # For ADA pairs, use the ADA side to calculate USD value
                # Note: tokens were potentially swapped above to ensure ADA is second (ticker_b)
                market_data = p.get("marketData", {})
                volume_24h_usd = None
                fees_24h_usd = None
                
                if market_data:
                    # Volume is in native token units (lovelace for ADA)
                    # After the swap above, token_b should be ADA for ADA pairs
                    vol_a_raw = Decimal(str(market_data.get("volumeA24h", 0) or 0))
                    vol_b_raw = Decimal(str(market_data.get("volumeB24h", 0) or 0))
                    fee_a_raw = Decimal(str(market_data.get("feeA24h", 0) or 0))
                    fee_b_raw = Decimal(str(market_data.get("feeB24h", 0) or 0))
                    
                    # If ticker_b is ADA, use volumeB (ADA side) for USD calculation
                    # The tokens were swapped earlier if needed, but marketData wasn't
                    # So we need to check original token positions
                    original_ticker_a = self._get_ticker(p.get("tokenA", {}), ticker_map)
                    original_ticker_b = self._get_ticker(p.get("tokenB", {}), ticker_map)
                    
                    if original_ticker_a == "ADA":
                        # tokenA is ADA, use volumeA
                        vol_ada = vol_a_raw / Decimal(1_000_000)  # lovelace to ADA
                        fee_ada = fee_a_raw / Decimal(1_000_000)
                        volume_24h_usd = vol_ada * Decimal(str(self.ada_price_usd))
                        fees_24h_usd = fee_ada * Decimal(str(self.ada_price_usd))
                    elif original_ticker_b == "ADA":
                        # tokenB is ADA, use volumeB
                        vol_ada = vol_b_raw / Decimal(1_000_000)
                        fee_ada = fee_b_raw / Decimal(1_000_000)
                        volume_24h_usd = vol_ada * Decimal(str(self.ada_price_usd))
                        fees_24h_usd = fee_ada * Decimal(str(self.ada_price_usd))
                    # For non-ADA pairs (like USDM-USDA), we can't easily calculate USD volume

                pool_metrics = WingRidersPoolMetrics(
                    pair=pair,
                    version=version,
                    pool_type=pool_type,
                    tvl_ada=tvl_ada,
                    tvl_usd=tvl_usd,
                    fees_apr=fees_apr,
                    staking_apr=staking_apr,
                    farm_apr=farm_apr,
                    boosting_apr=boosting_apr,
                    total_apr=total_apr,
                    reserve_a=reserve_a,
                    reserve_b=reserve_b,
                    ticker_a=ticker_a,
                    ticker_b=ticker_b,
                    has_farm=has_farm,
                    swap_fee_percent=swap_fee_percent,
                    volume_24h_usd=volume_24h_usd,
                    fees_24h_usd=fees_24h_usd,
                )
                pools.append(pool_metrics)
                seen_pairs.add(pair_key)

            except Exception as e:
                logger.warning("Error parsing pool data: %s", e)
                continue

        # Sort by TVL descending
        pools.sort(key=lambda x: x.tvl_usd or Decimal(0), reverse=True)
        
        farms_count = sum(1 for p in pools if p.has_farm)
        logger.info("Parsed %d WingRiders pools with TVL >= %s ADA (%d with active farms)", 
                   len(pools), self.min_tvl_ada, farms_count)
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

