"""Minswap protocol adapter for Cardano."""

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

import requests

from src.adapters.base import ProtocolAdapter

logger = logging.getLogger(__name__)


@dataclass
class PoolMetrics:
    """Container for pool metrics (APR, TVL, fees, volume).
    
    APR fields:
        apr: Minswap's trading_fee_apr (~30-day rolling average, trading fees only)
        apr_1d: Calculated total 1-day APR (trading fees + farming rewards)
        trading_fee_apr_1d: 1-day APR from trading fees only
        farming_apr_1d: 1-day APR from MIN farming rewards
    """
    apr: Optional[Decimal] = None       # Minswap's 30-day rolling average (trading fees only)
    apr_1d: Optional[Decimal] = None    # Total 1-day APR (fees + farming)
    trading_fee_apr_1d: Optional[Decimal] = None  # 1-day trading fee APR
    farming_apr_1d: Optional[Decimal] = None      # 1-day farming APR from MIN rewards
    tvl_usd: Optional[Decimal] = None
    fees_24h: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    swap_fee_percent: Optional[Decimal] = None  # Swap fee percentage (e.g., 0.30 for 0.30%)


class MinswapAdapter(ProtocolAdapter):
    """Adapter for querying Minswap pool/farm APRs."""

    # MIN-ADA pool LP asset for price fetching
    MIN_ADA_LP_ASSET = "f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c.82e2b1fd27a7712a1a9cf750dfbea1a5778611b20e06dd6a611df7a643f8cb75"
    
    # MIN farming rewards are now configured per-pool using daily_min_emission
    # Values come directly from https://minswap.org/analytics/yield-dashboard

    CANDIDATE_APR_KEYS = [
        "trading_fee_apr",  # exposed by /v1/pools/:id/metrics
        "apr",
        "apy",
        "farmApr",
        "farmApy",
        "farm_apr",
        "farm_apy",
        "lpApr",
        "lpApy",
        "lp_apr",
        "lp_apy",
        "combinedApr",
        "combinedApy",
    ]

    CANDIDATE_TVL_KEYS = [
        # USD values first (preferred)
        "liquidity_currency",  # Minswap API - TVL in USD
        "tvlUsd",
        "tvl_usd",
        # ADA values (need conversion but better than lovelace)
        "tvlAda",
        "tvl_ada",
        # Generic (often USD but verify)
        "tvl",
        "totalLiquidity",
        "total_liquidity",
        "lockedValue",
        "locked_value",
        # Lovelace (smallest unit - last resort, needs conversion)
        # "liquidity",  # Minswap returns this in lovelace - too large!
    ]

    CANDIDATE_FEES_24H_KEYS = [
        "trading_fee_24h",
        "fees_24h",
        "fees24h",
        "tradingFee24h",
        "fee24h",
    ]

    CANDIDATE_VOLUME_24H_KEYS = [
        "volume_24h",
        "volume24h",
        "tradingVolume24h",
        "trading_volume_24h",
    ]

    def __init__(self, protocol_name: str, config: Dict):
        super().__init__(protocol_name, config)
        self.base_url = config.get(
            "base_url", "https://api-mainnet-prod.minswap.org"
        ).rstrip("/")
        self.pairs = config.get("pairs", [])
        self.timeout = config.get("timeout", 10)
        self.max_retries = config.get("max_retries", 3)
        
        # Cache for MIN price (refreshed per collection run)
        self._min_price_cache: Optional[Decimal] = None
        self._min_price_cache_time: float = 0
        self._min_price_cache_ttl = 300  # 5 minutes

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "defitracker/1.0"})

    # ------------------------------------------------------------------ #
    # ProtocolAdapter interface
    # ------------------------------------------------------------------ #

    def get_supported_assets(self) -> List[str]:
        """Return the configured pair identifiers (e.g., NIGHT-ADA)."""
        assets = []
        for pair in self.pairs:
            assets.append(self._pair_label(pair))
        return assets

    def get_supply_apr(self, asset: str) -> Optional[Decimal]:
        """
        Fetch the current farm APR/APY for a configured pair.

        Args:
            asset: Display name configured for the pair (e.g., NIGHT-ADA)

        Returns:
            APR as Decimal (percentage) or None if unavailable.
        """
        metrics = self.get_pool_metrics(asset)
        return metrics.apr if metrics else None

    def get_min_price(self) -> Optional[Decimal]:
        """
        Fetch the current MIN token price in USD from the MIN-ADA pool.
        
        Returns:
            MIN price in USD, or None if unavailable.
        """
        now = time.time()
        if self._min_price_cache is not None and (now - self._min_price_cache_time) < self._min_price_cache_ttl:
            return self._min_price_cache
        
        payload = self._get_json(f"v1/pools/{self.MIN_ADA_LP_ASSET}/metrics")
        if not payload:
            logger.warning("Could not fetch MIN-ADA pool for MIN price")
            return self._min_price_cache  # Return stale cache if available
        
        try:
            # MIN price = ADA value / MIN tokens in pool
            # liquidity_a = ADA tokens, liquidity_b = MIN tokens
            # liquidity_a_currency = ADA value in USD
            liquidity_a_currency = payload.get("liquidity_a_currency")
            liquidity_b = payload.get("liquidity_b")
            
            if liquidity_a_currency and liquidity_b and float(liquidity_b) > 0:
                min_price = Decimal(str(liquidity_a_currency)) / Decimal(str(liquidity_b))
                self._min_price_cache = min_price
                self._min_price_cache_time = now
                logger.info("MIN token price: $%.6f", min_price)
                return min_price
        except Exception as e:
            logger.error("Error calculating MIN price: %s", e)
        
        return self._min_price_cache

    def get_pool_metrics(self, asset: str) -> Optional[PoolMetrics]:
        """
        Fetch pool metrics (APR and TVL) for a configured pair.

        Args:
            asset: Display name configured for the pair (e.g., NIGHT-ADA)

        Returns:
            PoolMetrics with apr and tvl_usd, or None if unavailable.
        """
        pair = self._find_pair_config(asset)
        if not pair:
            logger.warning("Asset %s not configured for Minswap", asset)
            return None

        payload = self._fetch_pair_payload(pair)
        if payload is None:
            return None

        metrics = PoolMetrics()

        # Extract APR (30-day trading fee APR from API)
        apr_value = self._extract_apr(payload)
        if apr_value is not None:
            try:
                metrics.apr = Decimal(str(apr_value))
            except Exception:
                logger.error("Could not convert APR value %s for %s", apr_value, asset)

        # Extract TVL (using liquidity_currency for USD value)
        tvl_value = self._extract_tvl(payload)
        if tvl_value is not None:
            try:
                metrics.tvl_usd = Decimal(str(tvl_value))
            except Exception:
                logger.error("Could not convert TVL value %s for %s", tvl_value, asset)

        # Extract 24h fees
        fees_value = self._extract_field(payload, self.CANDIDATE_FEES_24H_KEYS)
        if fees_value is not None:
            try:
                metrics.fees_24h = Decimal(str(fees_value))
            except Exception:
                logger.error("Could not convert fees_24h value %s for %s", fees_value, asset)

        # Extract 24h volume
        volume_value = self._extract_field(payload, self.CANDIDATE_VOLUME_24H_KEYS)
        if volume_value is not None:
            try:
                metrics.volume_24h = Decimal(str(volume_value))
            except Exception:
                logger.error("Could not convert volume_24h value %s for %s", volume_value, asset)

        # Extract swap fee (trading_fee_tier is an array like [0.3, 0.3] for buy/sell)
        swap_fee = self._extract_swap_fee(payload)
        if swap_fee is not None:
            try:
                metrics.swap_fee_percent = Decimal(str(swap_fee))
            except Exception:
                logger.error("Could not convert swap_fee value %s for %s", swap_fee, asset)

        # Calculate 1-day trading fee APR
        if metrics.fees_24h is not None and metrics.tvl_usd is not None and metrics.tvl_usd > 0:
            try:
                # Trading Fee APR = (daily_fees / TVL) * 365 * 100
                metrics.trading_fee_apr_1d = (metrics.fees_24h / metrics.tvl_usd) * Decimal(365) * Decimal(100)
            except Exception:
                logger.error("Could not calculate trading_fee_apr_1d for %s", asset)

        # Calculate farming APR from MIN rewards
        farming_apr = self._calculate_farming_apr(pair, metrics.tvl_usd)
        if farming_apr is not None:
            metrics.farming_apr_1d = farming_apr

        # Total 1-day APR = trading fee APR + farming APR
        if metrics.trading_fee_apr_1d is not None:
            metrics.apr_1d = metrics.trading_fee_apr_1d
            if metrics.farming_apr_1d is not None:
                metrics.apr_1d += metrics.farming_apr_1d

        return metrics

    def _calculate_farming_apr(self, pair: Dict, tvl_usd: Optional[Decimal]) -> Optional[Decimal]:
        """
        Calculate the farming APR from MIN token rewards.
        
        Uses the daily_min_emission value configured per-pool from the Minswap
        yield dashboard (https://minswap.org/analytics/yield-dashboard).
        
        Formula: Farming APR = (daily_min_emission * MIN_price / TVL) * 365 * 100
        
        Args:
            pair: Pool configuration dict (should include 'daily_min_emission')
            tvl_usd: Pool's total value locked in USD
            
        Returns:
            Farming APR as Decimal percentage, or None if cannot calculate.
        """
        if tvl_usd is None or tvl_usd <= 0:
            return None
        
        # Get daily MIN emission from config (set in chains.yaml, from yield dashboard)
        daily_min_emission = pair.get("daily_min_emission")
        if daily_min_emission is None or float(daily_min_emission) <= 0:
            # No farming rewards configured for this pool
            return None
        
        daily_min_emission = Decimal(str(daily_min_emission))
        
        # Get MIN price
        min_price = self.get_min_price()
        if min_price is None:
            logger.warning("Could not get MIN price for farming APR calculation")
            return None
        
        try:
            # Daily reward value in USD
            daily_reward_usd = daily_min_emission * min_price
            
            # Farming APR = (daily_reward_value / TVL) * 365 * 100
            farming_apr = (daily_reward_usd / tvl_usd) * Decimal(365) * Decimal(100)
            
            logger.debug(
                "Farming APR for pool: daily_min=%.2f, min_price=$%.6f, "
                "daily_value=$%.2f, tvl=$%.2f, apr=%.2f%%",
                daily_min_emission, min_price,
                daily_reward_usd, tvl_usd, farming_apr
            )
            
            return farming_apr
        except Exception as e:
            logger.error("Error calculating farming APR: %s", e)
            return None

    def compute_apr_from_onchain(self, asset: str, lookback_days: int = 7) -> Optional[Decimal]:
        """On-chain computation is not implemented for Cardano Minswap."""
        logger.info(
            "On-chain APR computation not supported for Minswap (asset=%s, lookback=%s)",
            asset,
            lookback_days,
        )
        return None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _pair_label(self, pair_cfg: Dict) -> str:
        """Build a human-friendly label for the pair."""
        if pair_cfg.get("symbol"):
            return pair_cfg["symbol"]
        if pair_cfg.get("name"):
            return pair_cfg["name"]
        if pair_cfg.get("token_a") and pair_cfg.get("token_b"):
            return f"{pair_cfg['token_a']}-{pair_cfg['token_b']}"
        return pair_cfg.get("pool_id") or pair_cfg.get("farm_id") or "unknown"

    def _find_pair_config(self, asset: str) -> Optional[Dict]:
        for pair in self.pairs:
            if self._pair_label(pair).lower() == asset.lower():
                return pair
        return None

    def _fetch_pair_payload(self, pair: Dict) -> Optional[Dict]:
        """
        Attempt to fetch pool/farm data for a pair.

        Preferred: /v1/pools/{lp_asset}/metrics where lp_asset is
        {policy}.{token_name} or {policy}{token_name}.
        """
        farm_id = pair.get("farm_id")
        pool_id = pair.get("pool_id")

        # Try pool metrics endpoint (with dot and without dot)
        if farm_id and pool_id:
            lp_with_dot = f"{farm_id}.{pool_id}"
            lp_concat = f"{farm_id}{pool_id}"
            for lp in (lp_with_dot, lp_concat):
                payload = self._get_json(f"v1/pools/{lp}/metrics")
                if payload:
                    return payload

        # Fallback to generic metrics search if configured
        if pool_id:
            payload = self._post_json("v1/pools/metrics", {"term": pool_id, "limit": 5})
            if payload and isinstance(payload, dict):
                metrics = payload.get("pool_metrics") or []
                if metrics:
                    return metrics[0]

        logger.warning(
            "No payload retrieved for pair %s (farm_id=%s, pool_id=%s)",
            self._pair_label(pair),
            farm_id,
            pool_id,
        )
        return None

    def _get_json(self, path: str) -> Optional[Dict]:
        """HTTP GET with basic backoff handling."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        backoff = 2

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code == 429:
                    retry_after = (
                        int(resp.headers.get("Retry-After", backoff))
                        if str(resp.headers.get("Retry-After", "")).isdigit()
                        else backoff
                    )
                    logger.warning(
                        "Rate limited by Minswap API (attempt %s/%s). Sleeping %ss",
                        attempt,
                        self.max_retries,
                        retry_after,
                    )
                    time.sleep(retry_after)
                    backoff = min(backoff * 2, 30)
                    continue

                if resp.status_code >= 400:
                    logger.error(
                        "Minswap API error %s for %s: %s",
                        resp.status_code,
                        url,
                        resp.text,
                    )
                    return None

                return resp.json()
            except requests.RequestException as exc:
                logger.error(
                    "Error calling Minswap API (attempt %s/%s) %s: %s",
                    attempt,
                    self.max_retries,
                    url,
                    exc,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

        return None

    def _post_json(self, path: str, body: Dict) -> Optional[Dict]:
        """HTTP POST with basic backoff handling."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        backoff = 2

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(url, json=body, timeout=self.timeout)
                if resp.status_code == 429:
                    retry_after = (
                        int(resp.headers.get("Retry-After", backoff))
                        if str(resp.headers.get("Retry-After", "")).isdigit()
                        else backoff
                    )
                    logger.warning(
                        "Rate limited by Minswap API (attempt %s/%s). Sleeping %ss",
                        attempt,
                        self.max_retries,
                        retry_after,
                    )
                    time.sleep(retry_after)
                    backoff = min(backoff * 2, 30)
                    continue

                if resp.status_code >= 400:
                    logger.error(
                        "Minswap API error %s for %s: %s",
                        resp.status_code,
                        url,
                        resp.text,
                    )
                    return None

                return resp.json()
            except requests.RequestException as exc:
                logger.error(
                    "Error calling Minswap API (attempt %s/%s) %s: %s",
                    attempt,
                    self.max_retries,
                    url,
                    exc,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

        return None

    def _extract_apr(self, payload: Dict) -> Optional[float]:
        """
        Extract an APR/APY value from the API payload.

        The Minswap API is not formally documented; we scan a few common keys.
        """
        if not isinstance(payload, dict):
            return None

        for key in self.CANDIDATE_APR_KEYS:
            if key in payload and payload[key] is not None:
                return payload[key]

        # Nested locations we often see: 'farm', 'statistics', 'data'
        for nested in ("farm", "statistics", "data"):
            nested_value = payload.get(nested)
            if isinstance(nested_value, dict):
                apr = self._extract_apr(nested_value)
                if apr is not None:
                    return apr

        return None

    def _extract_tvl(self, payload: Dict) -> Optional[float]:
        """
        Extract TVL (Total Value Locked) from the API payload.

        Looks for common TVL keys in the Minswap API response.
        Returns value in USD if available, otherwise in ADA.
        """
        return self._extract_field(payload, self.CANDIDATE_TVL_KEYS)

    def _extract_field(self, payload: Dict, candidate_keys: List[str]) -> Optional[float]:
        """
        Extract a numeric field from the API payload by trying candidate keys.

        Args:
            payload: API response dict
            candidate_keys: List of possible key names to try

        Returns:
            Field value or None if not found
        """
        if not isinstance(payload, dict):
            return None

        for key in candidate_keys:
            if key in payload and payload[key] is not None:
                return payload[key]

        # Nested locations we often see: 'pool', 'statistics', 'data'
        for nested in ("pool", "statistics", "data"):
            nested_value = payload.get(nested)
            if isinstance(nested_value, dict):
                value = self._extract_field(nested_value, candidate_keys)
                if value is not None:
                    return value

        return None

    def _extract_swap_fee(self, payload: Dict) -> Optional[float]:
        """
        Extract swap fee percentage from the API payload.
        
        Minswap uses 'trading_fee_tier' which is an array like [0.3, 0.3]
        where the first element is the buy fee and the second is the sell fee.
        We return the first element (typically same for buy/sell).
        """
        if not isinstance(payload, dict):
            return None

        # Try direct key
        fee_tier = payload.get('trading_fee_tier')
        if fee_tier is not None and isinstance(fee_tier, list) and len(fee_tier) > 0:
            return fee_tier[0]

        # Try nested locations
        for nested in ("pool", "statistics", "data"):
            nested_value = payload.get(nested)
            if isinstance(nested_value, dict):
                fee_tier = nested_value.get('trading_fee_tier')
                if fee_tier is not None and isinstance(fee_tier, list) and len(fee_tier) > 0:
                    return fee_tier[0]

        return None

