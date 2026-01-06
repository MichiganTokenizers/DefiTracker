"""MuesliSwap protocol adapter for Cardano.

MuesliSwap is a decentralized exchange (DEX) on Cardano that operates as an
aggregator with its own orderbook and liquidity pools.

API provides:
- Pool data (reserves, trading pairs, fees)
- Pool identifiers and LP tokens
- Price information

API Base: https://onchain2.muesliswap.com/pools
Note: No 24h volume data available from API, so APR cannot be calculated.
Only TVL data is tracked.
"""

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import requests

from src.adapters.base import ProtocolAdapter

logger = logging.getLogger(__name__)


@dataclass
class MuesliSwapPoolMetrics:
    """Container for MuesliSwap pool metrics."""
    pool_id: str
    pair: str
    token_a: str
    token_b: str
    tvl_ada: Optional[Decimal] = None
    tvl_usd: Optional[Decimal] = None
    reserve_a: Optional[Decimal] = None
    reserve_b: Optional[Decimal] = None
    fee_percent: Optional[Decimal] = None
    price: Optional[Decimal] = None  # Price of tokenB in terms of tokenA
    provider: str = "muesliswap"  # Pool provider (muesliswap, minswap, etc)
    # Note: No volume data available from API
    volume_24h_ada: Optional[Decimal] = None
    volume_24h_usd: Optional[Decimal] = None
    fees_24h_usd: Optional[Decimal] = None
    apr: Optional[Decimal] = None  # Cannot be calculated without volume data


class MuesliSwapAdapter(ProtocolAdapter):
    """Adapter for querying MuesliSwap pool data."""

    def __init__(self, protocol_name: str, config: Dict):
        super().__init__(protocol_name, config)
        self.base_url = config.get("base_url", "https://onchain2.muesliswap.com")
        self.timeout = config.get("timeout", 30)
        self.max_retries = config.get("max_retries", 3)
        # 1000 ADA minimum TVL as requested
        self.min_tvl_ada = config.get("min_tvl_ada", 1000)
        self.min_tvl_usd = config.get("min_tvl_usd", 0)
        self.ada_price_usd = config.get("ada_price_usd", 0.35)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "defitracker/1.0",
            "Accept": "application/json",
        })

        # Cache for pool data
        self._pool_cache: List[MuesliSwapPoolMetrics] = []
        self._cache_timestamp: float = 0
        self._cache_ttl = config.get("cache_ttl", 300)

    def get_supported_assets(self) -> List[str]:
        """Return list of pool pair names with TVL above threshold."""
        pools = self._get_pools()
        return [p.pair for p in pools]

    def get_supply_apr(self, asset: str) -> Optional[Decimal]:
        """
        Get the APR for a pool.
        
        Note: MuesliSwap API does not provide volume data, so APR cannot
        be calculated from trading fees. Returns None.
        
        Args:
            asset: Pool pair name (e.g., "ADA-MIN")
            
        Returns:
            None (volume data not available)
        """
        pools = self._get_pools()
        for pool in pools:
            if pool.pair == asset:
                return pool.apr
        return None

    def get_pool_metrics(self, asset: str) -> Optional[MuesliSwapPoolMetrics]:
        """
        Get full pool metrics for a pair.
        
        Args:
            asset: Pool pair name (e.g., "ADA-MIN")
            
        Returns:
            MuesliSwapPoolMetrics or None if not found
        """
        pools = self._get_pools()
        for pool in pools:
            if pool.pair == asset:
                return pool
        return None

    def get_all_pools(self) -> List[MuesliSwapPoolMetrics]:
        """Get all pools meeting the TVL threshold."""
        return self._get_pools()

    def compute_apr_from_onchain(self, asset: str, lookback_days: int = 7) -> Optional[Decimal]:
        """On-chain computation not available for Cardano."""
        logger.info(
            "On-chain APR computation not supported for MuesliSwap (asset=%s)",
            asset,
        )
        return None

    def _get_pools(self) -> List[MuesliSwapPoolMetrics]:
        """Fetch and cache pool data from the API."""
        now = time.time()
        if now - self._cache_timestamp < self._cache_ttl and self._pool_cache:
            return self._pool_cache

        pools = self._fetch_pools()
        if pools:
            self._pool_cache = pools
            self._cache_timestamp = now

        return self._pool_cache

    def _fetch_pools(self) -> List[MuesliSwapPoolMetrics]:
        """Fetch pools from the MuesliSwap API."""
        url = f"{self.base_url.rstrip('/')}/pools"
        backoff = 2

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", backoff))
                    logger.warning(
                        "Rate limited by MuesliSwap API. Sleeping %ss",
                        retry_after
                    )
                    time.sleep(retry_after)
                    backoff = min(backoff * 2, 30)
                    continue

                if resp.status_code >= 400:
                    logger.error(
                        "MuesliSwap API error %s: %s",
                        resp.status_code, resp.text[:200]
                    )
                    return []

                data = resp.json()
                if not isinstance(data, list):
                    logger.error("Unexpected response format from MuesliSwap API")
                    return []

                pools = self._parse_pools(data)
                logger.info(
                    "Fetched %d MuesliSwap pools with TVL >= %d ADA",
                    len(pools), self.min_tvl_ada
                )
                return pools

            except requests.RequestException as exc:
                logger.error(
                    "Error fetching from MuesliSwap API (attempt %s/%s): %s",
                    attempt, self.max_retries, exc
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

        return []

    def _parse_pools(self, raw_pools: List[Dict]) -> List[MuesliSwapPoolMetrics]:
        """Parse raw pool data into MuesliSwapPoolMetrics objects."""
        pools = []
        seen_pairs = set()

        for p in raw_pools:
            try:
                pool_metrics = self._parse_single_pool(p)
                if pool_metrics is None:
                    continue

                # Apply TVL filters
                if pool_metrics.tvl_ada is None:
                    continue
                if pool_metrics.tvl_ada < self.min_tvl_ada:
                    continue
                if self.min_tvl_usd > 0 and pool_metrics.tvl_usd is not None:
                    if pool_metrics.tvl_usd < self.min_tvl_usd:
                        continue

                # Skip duplicates (keep highest TVL version)
                if pool_metrics.pair in seen_pairs:
                    continue

                pools.append(pool_metrics)
                seen_pairs.add(pool_metrics.pair)

            except Exception as e:
                logger.debug("Error parsing pool data: %s", e)
                continue

        # Sort by TVL descending
        pools.sort(key=lambda x: x.tvl_ada or Decimal(0), reverse=True)

        return pools

    def _parse_single_pool(self, p: Dict) -> Optional[MuesliSwapPoolMetrics]:
        """Parse a single pool from the API response.
        
        MuesliSwap API format:
        {
            "provider": "muesliswap",
            "fee": "0.3",
            "tokenA": {"amount": "15943144517", "token": "."},
            "tokenB": {"amount": "81940", "token": "8a1cfae...4d494c4b"},
            "price": 194570.96,
            "poolId": "7a8041a0...c535fb4e",
            ...
        }
        
        Token format: "." for ADA, or "{policyId}.{assetNameHex}"
        Amount: In smallest unit (lovelace for ADA)
        """
        token_a_data = p.get("tokenA", {})
        token_b_data = p.get("tokenB", {})

        token_a_str = token_a_data.get("token", "")
        token_b_str = token_b_data.get("token", "")

        # Check which token is ADA (represented as ".")
        is_a_ada = token_a_str == "." or token_a_str == ""
        is_b_ada = token_b_str == "." or token_b_str == ""

        # Only track pools that have ADA as one of the tokens
        # This ensures we can calculate TVL accurately
        if not is_a_ada and not is_b_ada:
            return None

        # Extract token info
        ticker_a, decimals_a = self._decode_token(token_a_str)
        ticker_b, decimals_b = self._decode_token(token_b_str)

        if not ticker_a or not ticker_b:
            return None

        # Skip pools where both tokens are the same
        if ticker_a == ticker_b:
            return None

        # Ensure ADA is always SECOND in the pair name (e.g., MILK-ADA, not ADA-MILK)
        # This matches the Minswap convention
        if is_a_ada and not is_b_ada:
            # Swap so ADA is second
            ticker_a, ticker_b = ticker_b, ticker_a
            token_a_data, token_b_data = token_b_data, token_a_data
            decimals_a, decimals_b = decimals_b, decimals_a
            is_a_ada, is_b_ada = is_b_ada, is_a_ada

        # Ensure pair name fits in database (max 20 chars for symbol column)
        pair = f"{ticker_a}-{ticker_b}"
        if len(pair) > 20:
            # Truncate ticker_a to fit (keep -ADA suffix)
            max_a_len = 20 - len(ticker_b) - 1
            if max_a_len > 0:
                ticker_a = ticker_a[:max_a_len]
                pair = f"{ticker_a}-{ticker_b}"
            else:
                pair = pair[:20]

        # Parse reserves (ADA is in lovelace, so divide by 1_000_000)
        # After swap: ticker_a is the non-ADA token, ticker_b is ADA
        try:
            amount_a = int(token_a_data.get("amount", 0))
            amount_b = int(token_b_data.get("amount", 0))
            
            # ticker_a is non-ADA token (after swap)
            reserve_a = Decimal(amount_a) / Decimal(10 ** decimals_a)
            # ticker_b is ADA (after swap) - always in lovelace (6 decimals)
            reserve_b = Decimal(amount_b) / Decimal(1_000_000)
        except (ValueError, TypeError):
            reserve_a = None
            reserve_b = None

        # Calculate TVL in ADA (2x the ADA reserve since it's a pair)
        # After swap, is_b_ada should be True (ADA is second)
        tvl_ada = None
        if is_b_ada and reserve_b is not None:
            tvl_ada = reserve_b * Decimal(2)

        tvl_usd = tvl_ada * Decimal(str(self.ada_price_usd)) if tvl_ada else None

        # Parse fee
        fee_percent = None
        try:
            fee_str = p.get("fee", "0.3")
            fee_percent = Decimal(str(fee_str))
        except (ValueError, TypeError):
            fee_percent = Decimal("0.3")

        # Parse price
        price = None
        try:
            price = Decimal(str(p.get("price", 0)))
        except (ValueError, TypeError):
            pass

        # Get pool ID and provider
        pool_id = p.get("poolId", "")
        provider = p.get("provider", "muesliswap")

        return MuesliSwapPoolMetrics(
            pool_id=pool_id,
            pair=pair,
            token_a=ticker_a,
            token_b=ticker_b,
            tvl_ada=tvl_ada,
            tvl_usd=tvl_usd,
            reserve_a=reserve_a,
            reserve_b=reserve_b,
            fee_percent=fee_percent,
            price=price,
            provider=provider,
            # Volume/APR not available
            volume_24h_ada=None,
            volume_24h_usd=None,
            fees_24h_usd=None,
            apr=None,
        )

    def _decode_token(self, token_str: str) -> Tuple[str, int]:
        """Decode token identifier to ticker and decimals.
        
        Args:
            token_str: Token identifier ("." for ADA, or "{policyId}.{assetNameHex}")
            
        Returns:
            Tuple of (ticker, decimals)
        """
        if not token_str or token_str == ".":
            return "ADA", 6

        # Format: {policyId}.{assetNameHex}
        if "." in token_str:
            parts = token_str.split(".", 1)
            if len(parts) == 2:
                asset_name_hex = parts[1]
                try:
                    ticker = bytes.fromhex(asset_name_hex).decode("utf-8", errors="ignore")
                    if ticker:
                        # Remove null bytes and control characters
                        ticker = ticker.strip().replace('\x00', '')
                        # Truncate to fit database constraints (max 15 chars to allow for pair names)
                        if len(ticker) > 15:
                            ticker = ticker[:15]
                        return ticker, 6  # Default to 6 decimals
                except Exception:
                    pass
                # Fallback to first 8 chars of hex
                return asset_name_hex[:8], 6

        return token_str[:8] if token_str else "???", 6
