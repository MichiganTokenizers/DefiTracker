"""Portfolio service for fetching user DeFi positions.

Fetches LP positions via Blockfrost API and lending positions from Liqwid Finance.
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests

from src.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)

# Blockfrost API configuration (free tier: 50,000 requests/day)
BLOCKFROST_API_URL = "https://cardano-mainnet.blockfrost.io/api/v0"
BLOCKFROST_API_KEY = os.environ.get("BLOCKFROST_API_KEY", "")

# Minswap API for pool data
MINSWAP_API_URL = "https://api-mainnet-prod.minswap.org"

# SundaeSwap GraphQL API
SUNDAESWAP_API_URL = "https://api.sundae.fi/graphql"
SUNDAESWAP_YIELD_API_URL = "https://api.yield.sundaeswap.finance/graphql"

# WingRiders GraphQL API
WINGRIDERS_API_URL = "https://api.mainnet.wingriders.com/graphql"

# Liqwid Finance GraphQL API
LIQWID_API_URL = "https://v2.api.liqwid.finance/graphql"

# Liqwid qToken (receipt token) policy IDs - used to detect supply positions
# Map: policy_id -> market_id
LIQWID_QTOKEN_POLICY_IDS = {
    "a04ce7a52545e5e33c2867e148898d9e667a69602285f6a1298f9d68": "Ada",
    "d753e0d193680fe32710379d3a1ec48087ce94f3831505b922c2894b": "AGIX",
    "f72166e9fac8297aeb553c19ffab14f51ae271c2cb26783ba289a3a5": "BTC",
    "dd55119962ca550cdd4219999b9e6d25fc9128f96c7dcb5e485286eb": "COPI",
    "8996bb07509defe0be6f0c39845a736b266c85a70d87ebfb66454a78": "DAI",
    "6df63e2fdde8b2c3b3396265b0cc824aa4fb999396b1c154280f6b0c": "DJED",
    "b122b2fc62557df9c3fd0b5c62a4b2c970a0d711560e0a8dd7b264f3": "ERG",
    "5f42994532b04f9f5bd4141c69364c5b7d33c85036146ee321799702": "ETH",
    "85fa65407b5321fa0e2ef9a3ec98e12a00c35871d7a620be3132003c": "EURC",
    "f60b7232837203d335cd77494d25c1cc0b218b9a8f3459730c521d13": "IAG",
    "d15c36d6dec655677acb3318294f116ce01d8d9def3cc54cdd78909b": "IUSD",
    "3883e3e6a24e092d4c14e757fa8ef5c887853060def087d6cf5603f5": "LQ",
    "a4430a085f45bca6399bec6bd7514eb8c2fce1ed75c7554739cfc32b": "MIN",
    "c45fa8aefc662c003a32be67f6a4652d8ce56bd9e54d7696efd40c86": "NIGHT",
    "6f7d8e31d9256ec27f35d25659dd053cfec098032a5669b2b56798d0": "POL",
    "b8a327951d579d3537ea175078256bdf9f9899b5387b099d0b58f066": "PYUSD",
    "e1ff3557106fe13042ba0f772af6a2e43903ccfaaf03295048882c93": "SHEN",
    "4e8c49d610335d139ad7711e0f50315006e29b5221da531e365b4ef8": "SNEK",
    "aa280c98c5b07fdfc8d7a93fb5ba84510b421388e4a18e16efa8eb5f": "USDA",
    "aebcb6eaba17dea962008a9d693e39a3160b02b5b89b1c83e537c599": "USDC",
    "9e00df0615de0a7b121a7f961d43e23165b8e81b64786c6eb708d370": "USDM",
    "7a4d45e6b4e6835c4cea3968f291fab3704949cfd2f2dc1997c4eeec": "USDT",
    "f2636c8280e49e7ed7a7b1151341130989631b45a08d1b320f016981": "WMT",
}

# Known LP token policy IDs for Cardano DEXes
LP_POLICY_IDS = {
    "f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c": "minswap",
    "e4214b7cce62ac6fbba385d164df48e157eae5863521b4b67ca71d86": "sundaeswap",  # V1
    "e0302560ced2fdcbfcb2602697df970cd0d6a38f94b32703f51c312b": "sundaeswap",  # V3
    "026a18d04a0c642759bb3d83b12e3344894e5c1c7b2aeb1a2113a570": "wingriders",  # V1
    "6fdc63a1d71dc2c65502b79baae7fb543185702b12c3c5fb639ed737": "wingriders",  # V2
}

# SundaeSwap V3 LP policy ID (asset name contains pool ID)
SUNDAESWAP_V3_LP_POLICY = "e0302560ced2fdcbfcb2602697df970cd0d6a38f94b32703f51c312b"


@dataclass
class LPPosition:
    """Represents a user's LP position in a DEX pool (held in wallet)."""
    protocol: str
    pool: str
    lp_amount: str
    token_a: Dict[str, any]  # {symbol, amount}
    token_b: Dict[str, any]  # {symbol, amount}
    usd_value: Optional[float] = None
    current_apr: Optional[float] = None
    pool_share_percent: Optional[float] = None
    # Impermanent loss fields
    entry_date: Optional[str] = None  # ISO date when position was created
    entry_price_ratio: Optional[float] = None  # Token A price / Token B price at entry
    current_price_ratio: Optional[float] = None  # Current price ratio
    il_percent: Optional[float] = None  # Impermanent loss as percentage (negative = loss)
    il_usd: Optional[float] = None  # IL in USD terms

    def to_dict(self) -> Dict:
        return {
            "protocol": self.protocol,
            "pool": self.pool,
            "lp_amount": self.lp_amount,
            "token_a": self.token_a,
            "token_b": self.token_b,
            "usd_value": self.usd_value,
            "current_apr": self.current_apr,
            "pool_share_percent": self.pool_share_percent,
            "entry_date": self.entry_date,
            "entry_price_ratio": self.entry_price_ratio,
            "current_price_ratio": self.current_price_ratio,
            "il_percent": self.il_percent,
            "il_usd": self.il_usd,
        }


@dataclass
class FarmPosition:
    """Represents a user's staked LP position in a yield farm."""
    protocol: str
    pool: str
    lp_amount: str
    farm_type: str  # 'yield_farming', 'staking', etc.
    token_a: Dict[str, any]  # {symbol, amount}
    token_b: Dict[str, any]  # {symbol, amount}
    usd_value: Optional[float] = None  # Value in ADA
    current_apr: Optional[float] = None
    rewards_earned: Optional[float] = None
    pool_share_percent: Optional[float] = None
    # Impermanent loss fields
    entry_date: Optional[str] = None
    entry_price_ratio: Optional[float] = None
    current_price_ratio: Optional[float] = None
    il_percent: Optional[float] = None
    il_usd: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            "protocol": self.protocol,
            "pool": self.pool,
            "lp_amount": self.lp_amount,
            "farm_type": self.farm_type,
            "token_a": self.token_a,
            "token_b": self.token_b,
            "usd_value": self.usd_value,
            "current_apr": self.current_apr,
            "rewards_earned": self.rewards_earned,
            "pool_share_percent": self.pool_share_percent,
            "entry_date": self.entry_date,
            "entry_price_ratio": self.entry_price_ratio,
            "current_price_ratio": self.current_price_ratio,
            "il_percent": self.il_percent,
            "il_usd": self.il_usd,
        }


@dataclass
class LendingPosition:
    """Represents a user's lending/borrowing position."""
    protocol: str
    market: str
    position_type: str  # 'supply' or 'borrow'
    amount: float
    usd_value: Optional[float] = None
    current_apy: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            "protocol": self.protocol,
            "market": self.market,
            "type": self.position_type,
            "amount": self.amount,
            "usd_value": self.usd_value,
            "current_apy": self.current_apy,
        }


class PortfolioService:
    """Service for fetching and aggregating user DeFi positions."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "defitracker/1.0",
            "Content-Type": "application/json",
        })
        self.timeout = 15

        # Cache for pool metrics data
        self._pool_metrics_cache: Dict[str, Dict] = {}

        # Database connection for APR lookups
        self._db = DatabaseConnection()

    def _get_pool_apr_from_db(self, pool_name: str, protocol: str) -> Optional[float]:
        """
        Look up the latest APR for a pool from the database.

        Args:
            pool_name: Pool pair name (e.g., "NIGHT/ADA" or "ADA-NIGHT")
            protocol: Protocol name (e.g., "sundaeswap", "minswap", "wingriders")

        Returns:
            APR as float percentage, or None if not found
        """
        # Normalize pool name: convert "/" to "-" for database lookup
        # Database stores as "NIGHT-ADA", UI might have "NIGHT/ADA"
        db_pool_name = pool_name.replace("/", "-")

        # Also try with reversed order (ADA-NIGHT vs NIGHT-ADA)
        parts = db_pool_name.split("-")
        if len(parts) == 2:
            reversed_pool_name = f"{parts[1]}-{parts[0]}"
        else:
            reversed_pool_name = db_pool_name

        conn = self._db.get_connection()
        try:
            with conn.cursor() as cur:
                # Query for latest APR snapshot matching pool and protocol
                cur.execute("""
                    SELECT s.apr, s.farm_apr, s.fee_apr, s.staking_apr
                    FROM apr_snapshots s
                    JOIN assets a ON s.asset_id = a.asset_id
                    JOIN protocols p ON s.protocol_id = p.protocol_id
                    WHERE (LOWER(a.symbol) = LOWER(%s) OR LOWER(a.symbol) = LOWER(%s))
                      AND LOWER(p.name) = LOWER(%s)
                    ORDER BY s.timestamp DESC
                    LIMIT 1
                """, (db_pool_name, reversed_pool_name, protocol))

                row = cur.fetchone()
                if row:
                    # Return total APR (sum of all components if available)
                    base_apr = float(row[0]) if row[0] else 0
                    farm_apr = float(row[1]) if row[1] else 0
                    fee_apr = float(row[2]) if row[2] else 0
                    staking_apr = float(row[3]) if row[3] else 0

                    # If farm_apr is set, use it as total (already includes all components)
                    if farm_apr > 0:
                        return round(farm_apr, 2)
                    # Otherwise use base APR
                    return round(base_apr, 2) if base_apr > 0 else None

                return None
        except Exception as e:
            logger.debug("Error looking up APR for %s/%s: %s", pool_name, protocol, e)
            return None
        finally:
            self._db.return_connection(conn)

    def _normalize_pool_name(self, ticker_a: str, ticker_b: str) -> str:
        """
        Normalize pool pair name to standard format: TOKEN/ADA or TOKEN/STABLECOIN.

        Rules:
        1. ADA should always be second (e.g., NIGHT/ADA not ADA/NIGHT)
        2. For stablecoin pairs, use alphabetical order
        3. Common stablecoins: USDA, USDC, USDT, DJED, IUSD, DAI, USDM

        Args:
            ticker_a: First token ticker
            ticker_b: Second token ticker

        Returns:
            Normalized pool name in format "TOKEN/ADA" or "TOKEN/STABLECOIN"
        """
        stablecoins = {"USDA", "USDC", "USDT", "DJED", "IUSD", "DAI", "USDM", "EURC", "PYUSD"}

        # If ticker_a is ADA and ticker_b is not, swap them
        if ticker_a == "ADA" and ticker_b != "ADA":
            return f"{ticker_b}/ADA"

        # If ticker_b is ADA, keep as is
        if ticker_b == "ADA":
            return f"{ticker_a}/ADA"

        # For stablecoin pairs (no ADA), put stablecoin second
        if ticker_a in stablecoins and ticker_b not in stablecoins:
            return f"{ticker_b}/{ticker_a}"
        if ticker_b in stablecoins and ticker_a not in stablecoins:
            return f"{ticker_a}/{ticker_b}"

        # Both are stablecoins or neither - use alphabetical order
        if ticker_a <= ticker_b:
            return f"{ticker_a}/{ticker_b}"
        return f"{ticker_b}/{ticker_a}"

    def _get_lp_token_creation_date(
        self, wallet_address: str, policy_id: str, asset_name: str
    ) -> Optional[str]:
        """
        Find when an LP token was first received by querying Blockfrost asset history.

        Uses the asset transactions endpoint to find the earliest transaction where
        the wallet received this LP token. For staked/farmed LP tokens, we look for
        when the wallet first interacted with this LP token (either receiving it or
        sending it to a farm contract).

        Args:
            wallet_address: User's wallet address
            policy_id: LP token policy ID
            asset_name: LP token asset name (hex)

        Returns:
            ISO date string of first receipt, or None if not found
        """
        if not BLOCKFROST_API_KEY:
            return None

        asset_id = f"{policy_id}{asset_name}"
        # Get wallet address prefix for matching (first 30 chars covers payment key)
        wallet_prefix = wallet_address[:30] if len(wallet_address) > 30 else wallet_address

        try:
            # Get asset transaction history (ordered oldest first)
            url = f"{BLOCKFROST_API_URL}/assets/{asset_id}/transactions"
            headers = {"project_id": BLOCKFROST_API_KEY}
            params = {"order": "asc", "count": 100}

            resp = self.session.get(url, headers=headers, params=params, timeout=self.timeout)

            if resp.status_code != 200:
                logger.debug("Could not fetch asset transactions: %d", resp.status_code)
                return None

            transactions = resp.json()
            if not transactions:
                logger.debug("No transactions found for asset %s", asset_id[:20])
                return None

            logger.debug("Found %d transactions for LP token, checking for wallet involvement", len(transactions))

            # Find the first transaction where this wallet was involved with the LP token
            for tx_info in transactions:
                tx_hash = tx_info.get("tx_hash", "")
                block_time = tx_info.get("block_time")

                # Get transaction UTXOs to check wallet involvement
                utxo_url = f"{BLOCKFROST_API_URL}/txs/{tx_hash}/utxos"
                utxo_resp = self.session.get(utxo_url, headers=headers, timeout=self.timeout)

                if utxo_resp.status_code != 200:
                    continue

                utxo_data = utxo_resp.json()

                # Check if wallet received LP token in outputs
                for output in utxo_data.get("outputs", []):
                    output_addr = output.get("address", "")
                    if output_addr == wallet_address or output_addr.startswith(wallet_prefix):
                        for amount in output.get("amount", []):
                            if amount.get("unit") == asset_id:
                                # Wallet received LP token
                                if block_time:
                                    from datetime import datetime
                                    dt = datetime.utcfromtimestamp(block_time)
                                    logger.info("Found LP entry date (received): %s", dt.strftime("%Y-%m-%d"))
                                    return dt.strftime("%Y-%m-%d")

                # Also check if wallet sent LP token from inputs (for staked positions)
                # The first time the wallet interacted with this LP is when they got it
                for inp in utxo_data.get("inputs", []):
                    input_addr = inp.get("address", "")
                    if input_addr == wallet_address or input_addr.startswith(wallet_prefix):
                        for amount in inp.get("amount", []):
                            if amount.get("unit") == asset_id:
                                # Wallet sent LP token (e.g., to stake it)
                                # This means they had it before, but we need the receive date
                                # Continue searching for when they first received it
                                pass

            # If we couldn't find when wallet received it directly,
            # use the first transaction date as a fallback
            if transactions:
                first_tx = transactions[0]
                block_time = first_tx.get("block_time")
                if block_time:
                    from datetime import datetime
                    dt = datetime.utcfromtimestamp(block_time)
                    logger.info("Using first LP tx date as fallback: %s", dt.strftime("%Y-%m-%d"))
                    return dt.strftime("%Y-%m-%d")

            return None

        except Exception as e:
            logger.warning("Error fetching LP token creation date: %s", e)
            return None

    def _get_lp_entry_from_db(
        self, wallet_address: str, policy_id: str, asset_name: str
    ) -> Optional[Dict]:
        """
        Get stored LP entry data from database.

        Args:
            wallet_address: User's wallet address
            policy_id: LP token policy ID
            asset_name: LP token asset name (hex)

        Returns:
            Dict with entry_date, entry_price_ratio, etc. or None if not found
        """
        conn = self._db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT entry_date, entry_price_ratio, entry_tx_hash,
                           token_a_symbol, token_b_symbol, protocol, pool_name
                    FROM user_lp_entries
                    WHERE wallet_address = %s
                      AND policy_id = %s
                      AND asset_name = %s
                """, (wallet_address, policy_id, asset_name))

                row = cur.fetchone()
                if row:
                    return {
                        "entry_date": row[0].isoformat() if row[0] else None,
                        "entry_price_ratio": float(row[1]) if row[1] else None,
                        "entry_tx_hash": row[2],
                        "token_a_symbol": row[3],
                        "token_b_symbol": row[4],
                        "protocol": row[5],
                        "pool_name": row[6],
                    }
                return None

        except Exception as e:
            logger.debug("Error fetching LP entry from DB: %s", e)
            return None
        finally:
            self._db.return_connection(conn)

    def _store_lp_entry(
        self, wallet_address: str, policy_id: str, asset_name: str,
        protocol: str, pool_name: str, entry_date: str,
        entry_price_ratio: float, token_a_symbol: str, token_b_symbol: str,
        entry_tx_hash: Optional[str] = None
    ) -> bool:
        """
        Store LP entry data in database for future IL calculations.

        Args:
            wallet_address: User's wallet address
            policy_id: LP token policy ID
            asset_name: LP token asset name (hex)
            protocol: DEX protocol name
            pool_name: Pool name (e.g., "ADA/NIGHT")
            entry_date: ISO date string when position was created
            entry_price_ratio: Token A / Token B price ratio at entry
            token_a_symbol: Token A symbol
            token_b_symbol: Token B symbol
            entry_tx_hash: Transaction hash (optional)

        Returns:
            True if stored successfully
        """
        conn = self._db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_lp_entries (
                        wallet_address, policy_id, asset_name, protocol,
                        pool_name, entry_date, entry_price_ratio,
                        token_a_symbol, token_b_symbol, entry_tx_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (wallet_address, policy_id, asset_name)
                    DO NOTHING
                """, (
                    wallet_address, policy_id, asset_name, protocol,
                    pool_name, entry_date, entry_price_ratio,
                    token_a_symbol, token_b_symbol, entry_tx_hash
                ))
                conn.commit()
                return cur.rowcount > 0

        except Exception as e:
            logger.debug("Error storing LP entry: %s", e)
            conn.rollback()
            return False
        finally:
            self._db.return_connection(conn)

    def _calculate_current_price_ratio(self, lp_value_info: Dict) -> Optional[float]:
        """
        Calculate current price ratio from pool reserves.

        For a pool with Token A and Token B, the price ratio is:
        price_ratio = (Token B amount) / (Token A amount)

        This represents how many Token B you get for 1 Token A.

        Args:
            lp_value_info: Dict containing token_a and token_b with amounts

        Returns:
            Current price ratio, or None if cannot be calculated
        """
        try:
            token_a = lp_value_info.get("token_a", {})
            token_b = lp_value_info.get("token_b", {})

            amount_a = float(token_a.get("amount", 0) or 0)
            amount_b = float(token_b.get("amount", 0) or 0)
            symbol_a = token_a.get("symbol", "").upper()
            symbol_b = token_b.get("symbol", "").upper()

            if amount_a <= 0 or amount_b <= 0:
                return None

            # Normalize ratio to always be: ADA / OTHER_TOKEN
            # This ensures consistency regardless of token order in the pool
            if symbol_a == "ADA":
                # token_a is ADA: ratio = ADA / token_b
                ratio = amount_a / amount_b
            elif symbol_b == "ADA":
                # token_b is ADA: ratio = ADA / token_a
                ratio = amount_b / amount_a
            else:
                # No ADA in pair (rare), use token_b / token_a
                ratio = amount_b / amount_a

            logger.debug(
                "Price ratio for %s/%s: %.6f (normalized to ADA/OTHER)",
                symbol_a, symbol_b, ratio
            )
            return ratio

        except Exception as e:
            logger.debug("Error calculating current price ratio: %s", e)
            return None

    def _calculate_il_from_ratios(
        self, entry_ratio: float, current_ratio: float, current_value: Optional[float] = None
    ) -> Dict[str, Optional[float]]:
        """
        Calculate impermanent loss from price ratios.

        IL Formula: IL = 2 * sqrt(k) / (1 + k) - 1
        Where k = current_ratio / entry_ratio

        Args:
            entry_ratio: Token B / Token A ratio at entry
            current_ratio: Token B / Token A ratio now
            current_value: Current position value (for IL USD calculation)

        Returns:
            Dict with il_percent, il_usd
        """
        import math

        result = {
            "il_percent": None,
            "il_usd": None,
        }

        if not entry_ratio or not current_ratio or entry_ratio <= 0:
            return result

        try:
            # Price change ratio
            k = current_ratio / entry_ratio

            # IL formula
            sqrt_k = math.sqrt(k)
            il = (2 * sqrt_k / (1 + k)) - 1

            # Convert to percentage
            il_percent = round(il * 100, 2)
            result["il_percent"] = il_percent

            # Calculate USD impact
            if current_value and il != 0:
                hodl_value = current_value / (1 + il)
                il_usd = current_value - hodl_value
                result["il_usd"] = round(il_usd, 2)

            return result

        except Exception as e:
            logger.debug("Error calculating IL from ratios: %s", e)
            return result

    def _calculate_farm_position_il(
        self,
        wallet_address: str,
        policy_id: str,
        asset_name_hex: str,
        protocol: str,
        pool_name: str,
        lp_value_info: Dict,
    ) -> Dict[str, any]:
        """
        Calculate impermanent loss data for a farm position.

        This method encapsulates the IL calculation logic to be reused by all
        farm position fetching methods (WingRiders, SundaeSwap, Minswap).

        Args:
            wallet_address: User's wallet address
            policy_id: LP token policy ID
            asset_name_hex: LP token asset name (hex encoded)
            protocol: Protocol name (minswap, sundaeswap, wingriders)
            pool_name: Human-readable pool name (e.g., "NIGHT/ADA")
            lp_value_info: Dict with token_a, token_b info for ratio calculation

        Returns:
            Dict with IL fields: entry_date, entry_price_ratio, current_price_ratio,
                                 il_percent, il_usd
        """
        il_data = {
            "entry_date": None,
            "entry_price_ratio": None,
            "current_price_ratio": None,
            "il_percent": None,
            "il_usd": None,
        }

        try:
            # Get token symbols for validation
            token_a_info = lp_value_info.get("token_a", {})
            token_b_info = lp_value_info.get("token_b", {})
            token_a_symbol = token_a_info.get("symbol", "?")
            token_b_symbol = token_b_info.get("symbol", "?")

            logger.info(
                "Farm IL calculation for %s (%s): token_a=%s, token_b=%s",
                pool_name, protocol, token_a_symbol, token_b_symbol
            )

            if token_a_symbol == "?" or token_b_symbol == "?":
                logger.debug("Skipping IL calculation - missing token symbols")
                return il_data

            # Calculate current price ratio from reserves
            current_ratio = self._calculate_current_price_ratio(lp_value_info)
            if current_ratio:
                il_data["current_price_ratio"] = round(current_ratio, 6)

            # Check if we have stored entry data
            stored_entry = self._get_lp_entry_from_db(
                wallet_address, policy_id, asset_name_hex
            )
            logger.info(
                "Farm DB lookup for %s: stored_entry=%s, current_ratio=%s",
                pool_name, stored_entry, current_ratio
            )

            if stored_entry and stored_entry.get("entry_price_ratio"):
                # Use stored entry data
                il_data["entry_date"] = stored_entry["entry_date"]
                il_data["entry_price_ratio"] = stored_entry["entry_price_ratio"]

                # Calculate IL from ratios
                if current_ratio:
                    il_result = self._calculate_il_from_ratios(
                        stored_entry["entry_price_ratio"],
                        current_ratio,
                        lp_value_info.get("ada_value")
                    )
                    il_data.update(il_result)
                    logger.info(
                        "Calculated farm IL for %s: %.2f%% (entry: %s, ratio: %.4f -> %.4f)",
                        pool_name, il_result.get("il_percent", 0),
                        stored_entry["entry_date"],
                        stored_entry["entry_price_ratio"], current_ratio
                    )
            else:
                # First time seeing this position - get entry date and store
                logger.info("No stored entry for farm %s, fetching creation date...", pool_name)
                entry_date = self._get_lp_token_creation_date(
                    wallet_address, policy_id, asset_name_hex
                )
                logger.info("Got entry_date=%s for farm %s", entry_date, pool_name)

                if entry_date and current_ratio:
                    # Try to fetch historical price ratio at entry date
                    historical_ratio = None

                    if protocol == "minswap":
                        # Direct lookup for Minswap positions
                        historical_ratio = self._get_minswap_historical_price_ratio(
                            policy_id, asset_name_hex, entry_date
                        )
                    else:
                        # For SundaeSwap/WingRiders, search Minswap by token symbols
                        # (price ratios should be similar across DEXes due to arbitrage)
                        logger.info(
                            "Searching Minswap for historical price: %s/%s at %s",
                            token_a_symbol, token_b_symbol, entry_date
                        )
                        historical_ratio = self._get_historical_price_by_tokens(
                            token_a_symbol, token_b_symbol, entry_date
                        )
                        if historical_ratio:
                            logger.info(
                                "Using Minswap historical price for %s %s position: %.6f",
                                protocol, pool_name, historical_ratio
                            )
                        else:
                            logger.info(
                                "No Minswap historical price found for %s %s",
                                protocol, pool_name
                            )

                    # Use historical ratio if available, otherwise use current
                    entry_ratio = historical_ratio if historical_ratio else current_ratio
                    ratio_source = "historical" if historical_ratio else "current"

                    self._store_lp_entry(
                        wallet_address=wallet_address,
                        policy_id=policy_id,
                        asset_name=asset_name_hex,
                        protocol=protocol,
                        pool_name=pool_name,
                        entry_date=entry_date,
                        entry_price_ratio=entry_ratio,
                        token_a_symbol=token_a_symbol,
                        token_b_symbol=token_b_symbol,
                    )
                    il_data["entry_date"] = entry_date
                    il_data["entry_price_ratio"] = round(entry_ratio, 6)

                    # Calculate IL if we have historical data
                    if historical_ratio:
                        il_result = self._calculate_il_from_ratios(
                            entry_ratio, current_ratio, lp_value_info.get("ada_value")
                        )
                        il_data.update(il_result)
                        logger.info(
                            "Stored farm LP entry for %s with %s ratio: date=%s, entry=%.4f, current=%.4f, IL=%.2f%%",
                            pool_name, ratio_source, entry_date, entry_ratio, current_ratio,
                            il_result.get("il_percent", 0)
                        )
                    else:
                        # No historical data - IL starts at 0%
                        il_data["il_percent"] = 0.0
                        logger.info(
                            "Stored new farm LP entry for %s (no historical data): date=%s, ratio=%.4f",
                            pool_name, entry_date, entry_ratio
                        )

        except Exception as e:
            logger.warning("Error calculating farm position IL for %s: %s", pool_name, e)

        return il_data

    def _get_minswap_pool_metrics(self, policy_id: str, asset_name: str) -> Optional[Dict]:
        """
        Fetch pool metrics from Minswap API.

        Args:
            policy_id: LP token policy ID
            asset_name: LP token asset name (hex)

        Returns:
            Pool metrics dict with liquidity, reserves, APR, etc.
        """
        lp_asset = f"{policy_id}.{asset_name}"

        # Check cache first
        if lp_asset in self._pool_metrics_cache:
            return self._pool_metrics_cache[lp_asset]

        try:
            url = f"{MINSWAP_API_URL}/v1/pools/{lp_asset}/metrics"
            resp = self.session.get(url, timeout=self.timeout)

            if resp.status_code == 200:
                data = resp.json()
                self._pool_metrics_cache[lp_asset] = data
                return data
            else:
                logger.debug("Minswap pool metrics not found for %s: %d", lp_asset[:30], resp.status_code)
        except Exception as e:
            logger.warning("Error fetching Minswap pool metrics: %s", e)

        return None

    def _get_minswap_historical_price_ratio(
        self, policy_id: str, asset_name: str, target_date: str
    ) -> Optional[float]:
        """
        Fetch historical price ratio from Minswap candlestick API.

        Uses the OHLCV candlestick endpoint to get the price ratio (token_b/token_a)
        at a specific date.

        Args:
            policy_id: LP token policy ID
            asset_name: LP token asset name (hex)
            target_date: ISO date string (e.g., "2024-06-15")

        Returns:
            Price ratio (close price) at the target date, or None if not found
        """
        from datetime import datetime, timedelta

        lp_asset = f"{policy_id}.{asset_name}"

        try:
            # Parse target date and create time range
            dt = datetime.strptime(target_date, "%Y-%m-%d")
            # Use start of day and end of day (UTC timestamps in milliseconds)
            start_time = int(dt.timestamp() * 1000)
            end_time = int((dt + timedelta(days=1)).timestamp() * 1000)

            url = f"{MINSWAP_API_URL}/v1/pools/{lp_asset}/price/candlestick"
            params = {
                "start_time": start_time,
                "end_time": end_time,
                "interval": "1d",  # Daily candles
                "limit": 1,
            }

            resp = self.session.get(url, params=params, timeout=self.timeout)

            if resp.status_code == 200:
                data = resp.json()
                # Data is list of candles: {open, high, low, close, volume, timestamp}
                if data and len(data) > 0:
                    candle = data[0]
                    close_price = candle.get("close")
                    if close_price:
                        price = float(close_price)

                        # The candlestick price is typically asset_a price in terms of asset_b
                        # We need to get pool info to know which is ADA and normalize
                        pool_metrics = self._get_minswap_pool_metrics(policy_id, asset_name)
                        if pool_metrics:
                            asset_a = pool_metrics.get("asset_a", {}).get("metadata", {})
                            asset_b = pool_metrics.get("asset_b", {}).get("metadata", {})
                            symbol_a = asset_a.get("ticker", asset_a.get("symbol", "")).upper()
                            symbol_b = asset_b.get("ticker", asset_b.get("symbol", "")).upper()

                            # Minswap price is asset_a priced in asset_b
                            # If asset_a is ADA: price is ADA/OTHER (already normalized)
                            # If asset_b is ADA: price is OTHER/ADA, need to invert to get ADA/OTHER
                            if symbol_b == "ADA" and symbol_a != "ADA":
                                # Invert to normalize to ADA/OTHER
                                price = 1.0 / price if price > 0 else price
                                logger.info(
                                    "Historical price for %s/%s at %s: %.6f (inverted to ADA/OTHER)",
                                    symbol_a, symbol_b, target_date, price
                                )
                            else:
                                logger.info(
                                    "Historical price for %s/%s at %s: %.6f",
                                    symbol_a, symbol_b, target_date, price
                                )
                        else:
                            logger.info(
                                "Got historical price for %s at %s: %.6f (no pool info for normalization)",
                                lp_asset[:30], target_date, price
                            )

                        return price
                logger.debug("No candlestick data for %s at %s", lp_asset[:30], target_date)
            else:
                logger.debug(
                    "Minswap candlestick API returned %d for %s",
                    resp.status_code, lp_asset[:30]
                )
        except Exception as e:
            logger.warning("Error fetching Minswap historical price: %s", e)

        return None

    def _get_historical_price_by_tokens(
        self, token_a_symbol: str, token_b_symbol: str, target_date: str
    ) -> Optional[float]:
        """
        Fetch historical price ratio from Minswap by searching for the pool by token symbols.

        This allows us to get historical prices for SundaeSwap/WingRiders positions
        by looking up the equivalent pool on Minswap.

        Args:
            token_a_symbol: First token symbol (e.g., "ADA")
            token_b_symbol: Second token symbol (e.g., "NIGHT")
            target_date: ISO date string (e.g., "2024-06-15")

        Returns:
            Price ratio (ADA/OTHER) at the target date, or None if not found
        """
        # Determine which token is ADA and which is the other
        if token_a_symbol.upper() == "ADA":
            search_token = token_b_symbol
        elif token_b_symbol.upper() == "ADA":
            search_token = token_a_symbol
        else:
            # No ADA in pair, can't search effectively
            logger.debug("No ADA in token pair %s/%s, skipping Minswap lookup", token_a_symbol, token_b_symbol)
            return None

        try:
            # Search for pool on Minswap by token name
            url = f"{MINSWAP_API_URL}/v1/pools/metrics"
            payload = {
                "term": search_token,
                "page": 1,
                "limit": 10,
            }

            resp = self.session.post(url, json=payload, timeout=self.timeout)

            if resp.status_code == 200:
                data = resp.json()
                pools = data.get("data", [])

                # Find the ADA pair pool
                for pool in pools:
                    asset_a = pool.get("asset_a", {}).get("metadata", {})
                    asset_b = pool.get("asset_b", {}).get("metadata", {})
                    ticker_a = asset_a.get("ticker", "").upper()
                    ticker_b = asset_b.get("ticker", "").upper()

                    # Check if this is the ADA/TOKEN pair we're looking for
                    is_ada_pair = (
                        (ticker_a == "ADA" and ticker_b == search_token.upper()) or
                        (ticker_b == "ADA" and ticker_a == search_token.upper())
                    )

                    if is_ada_pair:
                        # Found the pool - get LP asset info
                        lp_asset = pool.get("lp_asset", {})
                        policy_id = lp_asset.get("currency_symbol", "")
                        asset_name = lp_asset.get("token_name", "")

                        if policy_id and asset_name:
                            logger.info(
                                "Found Minswap pool for %s/ADA: %s.%s",
                                search_token, policy_id[:20], asset_name[:20]
                            )
                            # Now fetch historical price using the LP asset
                            return self._get_minswap_historical_price_ratio(
                                policy_id, asset_name, target_date
                            )

                logger.debug("No Minswap ADA/%s pool found in search results", search_token)
            else:
                logger.debug("Minswap pool search returned %d", resp.status_code)

        except Exception as e:
            logger.warning("Error searching Minswap for %s pool: %s", search_token, e)

        return None

    def _get_sundaeswap_pool_metrics(self, asset_name_hex: str) -> Optional[Dict]:
        """
        Fetch pool metrics from SundaeSwap GraphQL API.

        For V3 LP tokens, the asset name contains the pool ID:
        - First 4 bytes (8 hex chars): prefix "0014df10"
        - Remaining bytes: pool ID

        Args:
            asset_name_hex: LP token asset name in hex

        Returns:
            Pool metrics dict with TVL, reserves, token info, etc.
        """
        # Extract pool ID from asset name
        # V3 LP asset names start with "0014df10" followed by pool ID
        if asset_name_hex.startswith("0014df10"):
            pool_id = asset_name_hex[8:]  # Remove prefix to get pool ID
        else:
            pool_id = asset_name_hex

        cache_key = f"sundae_{pool_id}"
        if cache_key in self._pool_metrics_cache:
            return self._pool_metrics_cache[cache_key]

        try:
            query = """
            {
              pools {
                byId(id: "%s") {
                  id
                  version
                  assetA { ticker name policyId decimals }
                  assetB { ticker name policyId decimals }
                  assetLP { id policyId assetNameHex }
                  current {
                    tvl { quantity }
                    quantityA { quantity }
                    quantityB { quantity }
                    quantityLP { quantity }
                  }
                  bidFee
                }
              }
            }
            """ % pool_id

            resp = self.session.post(
                SUNDAESWAP_API_URL,
                json={"query": query},
                timeout=self.timeout
            )

            if resp.status_code == 200:
                data = resp.json()
                pool_data = data.get("data", {}).get("pools", {}).get("byId")

                if pool_data:
                    self._pool_metrics_cache[cache_key] = pool_data
                    return pool_data
                else:
                    logger.debug("SundaeSwap pool not found for ID: %s", pool_id[:20])
            else:
                logger.debug("SundaeSwap API error: %d", resp.status_code)

        except Exception as e:
            logger.warning("Error fetching SundaeSwap pool metrics: %s", e)

        return None

    def _calculate_sundaeswap_lp_value(self, lp_amount: str, pool_data: Dict) -> Dict:
        """
        Calculate the ADA value of SundaeSwap LP tokens.

        Args:
            lp_amount: User's LP token amount (string, raw units)
            pool_data: Pool data from SundaeSwap GraphQL API

        Returns:
            Dict with ada_value, token_a info, token_b info, pool_share
        """
        try:
            user_lp = int(lp_amount)
            current = pool_data.get("current", {})

            # Get total LP supply
            total_lp = int(current.get("quantityLP", {}).get("quantity", "0"))
            if total_lp <= 0:
                return {"ada_value": None, "token_a": {}, "token_b": {}}

            # Calculate user's share
            share = user_lp / total_lp

            # Get TVL and reserves (in lovelace/raw units)
            tvl_lovelace = int(current.get("tvl", {}).get("quantity", "0"))
            reserve_a = int(current.get("quantityA", {}).get("quantity", "0"))
            reserve_b = int(current.get("quantityB", {}).get("quantity", "0"))

            # Get token info
            asset_a = pool_data.get("assetA", {})
            asset_b = pool_data.get("assetB", {})

            ticker_a = asset_a.get("ticker", "?")
            ticker_b = asset_b.get("ticker", "?")
            decimals_a = asset_a.get("decimals", 6)
            decimals_b = asset_b.get("decimals", 6)

            # Convert reserves to human-readable amounts
            reserve_a_human = reserve_a / (10 ** decimals_a)
            reserve_b_human = reserve_b / (10 ** decimals_b)

            # User's share of each asset
            user_amount_a = reserve_a_human * share
            user_amount_b = reserve_b_human * share

            # TVL in ADA (lovelace / 1M)
            tvl_ada = tvl_lovelace / 1_000_000
            user_value_ada = tvl_ada * share

            return {
                "ada_value": round(user_value_ada, 2),
                "pool_share_percent": share,
                "token_a": {
                    "symbol": ticker_a,
                    "amount": round(user_amount_a, 6),
                },
                "token_b": {
                    "symbol": ticker_b,
                    "amount": round(user_amount_b, 6),
                },
                "apr": None,  # Would need to fetch HRA from ticks data
            }

        except Exception as e:
            logger.warning("Error calculating SundaeSwap LP value: %s", e)
            return {"ada_value": None, "token_a": {}, "token_b": {}}

    def _get_wingriders_pool_metrics(self, policy_id: str, asset_name_hex: str) -> Optional[Dict]:
        """
        Fetch pool metrics from WingRiders GraphQL API by LP token asset.

        Args:
            policy_id: LP token policy ID
            asset_name_hex: LP token asset name in hex

        Returns:
            Pool metrics dict with TVL, reserves, token info, APR, etc.
        """
        cache_key = f"wr_{policy_id}_{asset_name_hex}"
        if cache_key in self._pool_metrics_cache:
            return self._pool_metrics_cache[cache_key]

        try:
            # Query pool by LP asset
            query = """
            query GetPool($asset: AssetInput!) {
              liquidityPoolById(poolAsset: $asset) {
                ... on LiquidityPoolV1 {
                  version
                  tokenA { policyId assetName quantity }
                  tokenB { policyId assetName quantity }
                  tvlInAda
                  feesAPR
                  stakingAPR(timeframe: CURRENT_EPOCH)
                  issuedShareToken { quantity }
                }
                ... on LiquidityPoolV2 {
                  version
                  tokenA { policyId assetName quantity }
                  tokenB { policyId assetName quantity }
                  tvlInAda
                  feesAPR
                  stakingAPR(timeframe: CURRENT_EPOCH)
                  issuedShareToken { quantity }
                }
              }
              tokensMetadata(assets: [{policyId: "%s", assetName: "%s"}]) {
                ticker
                asset { policyId assetName }
              }
            }
            """

            # First get the pool data
            pool_query = """
            query GetPool($asset: AssetInput!) {
              liquidityPoolById(poolAsset: $asset) {
                ... on LiquidityPoolV1 {
                  version
                  tokenA { policyId assetName quantity }
                  tokenB { policyId assetName quantity }
                  tvlInAda
                  feesAPR
                  stakingAPR(timeframe: CURRENT_EPOCH)
                  issuedShareToken { quantity }
                }
                ... on LiquidityPoolV2 {
                  version
                  tokenA { policyId assetName quantity }
                  tokenB { policyId assetName quantity }
                  tvlInAda
                  feesAPR
                  stakingAPR(timeframe: CURRENT_EPOCH)
                  issuedShareToken { quantity }
                }
              }
            }
            """

            variables = {
                "asset": {
                    "policyId": policy_id,
                    "assetName": asset_name_hex,
                }
            }

            resp = self.session.post(
                WINGRIDERS_API_URL,
                json={"query": pool_query, "variables": variables},
                timeout=self.timeout
            )

            if resp.status_code != 200:
                logger.debug("WingRiders API error: %d", resp.status_code)
                return None

            data = resp.json()

            if "errors" in data and data["errors"]:
                logger.debug("WingRiders GraphQL errors: %s", data["errors"][:200])
                return None

            pool_data = data.get("data", {}).get("liquidityPoolById")

            if not pool_data:
                logger.debug("WingRiders pool not found for LP asset: %s...%s", policy_id[:10], asset_name_hex[:10])
                return None

            # Fetch token metadata to get tickers
            token_a = pool_data.get("tokenA", {})
            token_b = pool_data.get("tokenB", {})

            # Build metadata query for both tokens
            metadata_assets = []
            if token_a.get("policyId"):
                metadata_assets.append({"policyId": token_a["policyId"], "assetName": token_a.get("assetName", "")})
            if token_b.get("policyId"):
                metadata_assets.append({"policyId": token_b["policyId"], "assetName": token_b.get("assetName", "")})

            ticker_map = {"": "ADA"}  # Empty policyId is ADA

            if metadata_assets:
                metadata_query = """
                query GetMetadata($assets: [AssetInput!]!) {
                  tokensMetadata(assets: $assets) {
                    ticker
                    asset { policyId assetName }
                  }
                }
                """
                meta_resp = self.session.post(
                    WINGRIDERS_API_URL,
                    json={"query": metadata_query, "variables": {"assets": metadata_assets}},
                    timeout=self.timeout
                )

                if meta_resp.status_code == 200:
                    meta_data = meta_resp.json()
                    for m in meta_data.get("data", {}).get("tokensMetadata", []):
                        asset = m.get("asset", {})
                        key = f"{asset.get('policyId', '')}_{asset.get('assetName', '')}"
                        ticker_map[key] = m.get("ticker", "?")

            # Add ticker info to pool data
            pool_data["_ticker_map"] = ticker_map

            self._pool_metrics_cache[cache_key] = pool_data
            return pool_data

        except Exception as e:
            logger.warning("Error fetching WingRiders pool metrics: %s", e)

        return None

    def _calculate_wingriders_lp_value(self, lp_amount: str, pool_data: Dict) -> Dict:
        """
        Calculate the ADA value of WingRiders LP tokens.

        Args:
            lp_amount: User's LP token amount (string, raw units)
            pool_data: Pool data from WingRiders GraphQL API

        Returns:
            Dict with ada_value, token_a info, token_b info, pool_share, apr
        """
        try:
            user_lp = int(lp_amount)

            # Get total LP supply
            issued_share = pool_data.get("issuedShareToken", {})
            total_lp = int(issued_share.get("quantity", "0"))
            if total_lp <= 0:
                return {"ada_value": None, "token_a": {}, "token_b": {}}

            # Calculate user's share
            share = user_lp / total_lp

            # Get TVL in lovelace (string that may be decimal)
            tvl_raw = pool_data.get("tvlInAda")
            if tvl_raw:
                tvl_lovelace = float(tvl_raw)
                tvl_ada = tvl_lovelace / 1_000_000
            else:
                tvl_ada = 0

            user_value_ada = tvl_ada * share

            # Get token info
            token_a = pool_data.get("tokenA", {})
            token_b = pool_data.get("tokenB", {})
            ticker_map = pool_data.get("_ticker_map", {})

            # Get tickers
            def get_ticker(token):
                if not token.get("policyId"):
                    return "ADA"
                key = f"{token.get('policyId', '')}_{token.get('assetName', '')}"
                return ticker_map.get(key, "?")

            ticker_a = get_ticker(token_a)
            ticker_b = get_ticker(token_b)

            # Get reserves
            reserve_a = float(token_a.get("quantity", 0))
            reserve_b = float(token_b.get("quantity", 0))

            # Determine decimals (ADA is 6, most tokens are 6, some are 0)
            # For simplicity, assume 6 decimals for ADA, and try to detect for others
            decimals_a = 6 if not token_a.get("policyId") else 6
            decimals_b = 6 if not token_b.get("policyId") else 6

            reserve_a_human = reserve_a / (10 ** decimals_a)
            reserve_b_human = reserve_b / (10 ** decimals_b)

            # User's share of each asset
            user_amount_a = reserve_a_human * share
            user_amount_b = reserve_b_human * share

            # Calculate total APR (fees + staking)
            fees_apr = float(pool_data.get("feesAPR") or 0)
            staking_apr = float(pool_data.get("stakingAPR") or 0)
            total_apr = fees_apr + staking_apr

            return {
                "ada_value": round(user_value_ada, 2),
                "pool_share_percent": share,
                "token_a": {
                    "symbol": ticker_a,
                    "amount": round(user_amount_a, 6),
                },
                "token_b": {
                    "symbol": ticker_b,
                    "amount": round(user_amount_b, 6),
                },
                "apr": round(total_apr, 2) if total_apr > 0 else None,
            }

        except Exception as e:
            logger.warning("Error calculating WingRiders LP value: %s", e)
            return {"ada_value": None, "token_a": {}, "token_b": {}}

    def _calculate_lp_value(self, lp_amount: str, pool_metrics: Dict) -> Dict:
        """
        Calculate the ADA value of LP tokens based on pool metrics.

        Args:
            lp_amount: User's LP token amount (string, raw units)
            pool_metrics: Pool metrics from Minswap API

        Returns:
            Dict with ada_value, token_a info, token_b info
        """
        try:
            user_lp = int(lp_amount)
            total_lp = pool_metrics.get("liquidity", 0)

            if total_lp <= 0:
                return {"ada_value": None, "token_a": {}, "token_b": {}}

            # Calculate user's share of the pool
            share = user_lp / total_lp

            # Get pool reserves
            reserve_a = pool_metrics.get("liquidity_a", 0)  # ADA amount
            reserve_b = pool_metrics.get("liquidity_b", 0)  # Other token amount
            total_value_ada = pool_metrics.get("liquidity_currency", 0)  # Total TVL in ADA

            # Get token info
            asset_a = pool_metrics.get("asset_a", {})
            asset_b = pool_metrics.get("asset_b", {})
            metadata_a = asset_a.get("metadata", {})
            metadata_b = asset_b.get("metadata", {})

            # User's share of each asset
            user_ada = reserve_a * share
            user_token_b = reserve_b * share
            user_total_ada = total_value_ada * share

            return {
                "ada_value": round(user_total_ada, 2),
                "pool_share_percent": share,
                "token_a": {
                    "symbol": metadata_a.get("ticker", "ADA"),
                    "amount": round(user_ada, 6),
                },
                "token_b": {
                    "symbol": metadata_b.get("ticker", "?"),
                    "amount": round(user_token_b, 6),
                },
                "apr": pool_metrics.get("trading_fee_apr"),
            }
        except Exception as e:
            logger.warning("Error calculating LP value: %s", e)
            return {"ada_value": None, "token_a": {}, "token_b": {}}

    def get_all_positions(self, wallet_address: str) -> Dict:
        """
        Fetch all positions for a wallet address.

        Args:
            wallet_address: Cardano wallet address (bech32 format)

        Returns:
            Dict with lp_positions, farm_positions, lending_positions, and total_usd_value
        """
        lp_positions = self.get_lp_positions(wallet_address)
        farm_positions = self.get_farm_positions(wallet_address)
        lending_positions = self.get_lending_positions(wallet_address)

        total_usd = sum(
            p.usd_value or 0 for p in lp_positions
        ) + sum(
            p.usd_value or 0 for p in farm_positions
        ) + sum(
            p.usd_value or 0 for p in lending_positions if p.position_type == "supply"
        )

        return {
            "lp_positions": [p.to_dict() for p in lp_positions],
            "farm_positions": [p.to_dict() for p in farm_positions],
            "lending_positions": [p.to_dict() for p in lending_positions],
            "total_usd_value": round(total_usd, 2),
        }

    def get_lp_positions(self, wallet_address: str) -> List[LPPosition]:
        """
        Fetch LP positions using Blockfrost API.

        Args:
            wallet_address: Cardano wallet address

        Returns:
            List of LPPosition objects
        """
        if not BLOCKFROST_API_KEY:
            logger.warning("BLOCKFROST_API_KEY not configured. Cannot fetch LP positions.")
            return []

        return self._fetch_blockfrost_lp_positions(wallet_address)

    def _fetch_blockfrost_lp_positions(self, wallet_address: str) -> List[LPPosition]:
        """Fetch LP positions by scanning wallet assets via Blockfrost."""
        positions = []

        try:
            # Get all assets held by the address
            headers = {"project_id": BLOCKFROST_API_KEY}
            url = f"{BLOCKFROST_API_URL}/addresses/{wallet_address}"

            logger.debug("Fetching address info from Blockfrost for %s", wallet_address[:20])
            resp = self.session.get(url, headers=headers, timeout=self.timeout)

            if resp.status_code == 404:
                logger.debug("Address not found on Blockfrost: %s", wallet_address[:20])
                return positions

            if resp.status_code != 200:
                logger.warning("Blockfrost API error: %d - %s", resp.status_code, resp.text[:200])
                return positions

            address_data = resp.json()

            # Get the amounts (list of assets)
            amounts = address_data.get("amount", [])

            for asset in amounts:
                unit = asset.get("unit", "")
                quantity = asset.get("quantity", "0")

                # Skip lovelace (ADA)
                if unit == "lovelace":
                    continue

                # Check if this is an LP token (policy ID matches known DEX)
                # Asset unit format: {policy_id}{asset_name}
                if len(unit) >= 56:
                    policy_id = unit[:56]
                    asset_name_hex = unit[56:]

                    if policy_id in LP_POLICY_IDS:
                        protocol = LP_POLICY_IDS[policy_id]
                        position = self._create_lp_position_from_asset(
                            policy_id, asset_name_hex, quantity, protocol, wallet_address
                        )
                        if position:
                            positions.append(position)

            logger.info("Found %d LP positions from Blockfrost", len(positions))

        except requests.RequestException as e:
            logger.warning("Error fetching Blockfrost data: %s", e)
        except Exception as e:
            logger.error("Unexpected error parsing Blockfrost data: %s", e)

        return positions

    def _create_lp_position_from_asset(
        self, policy_id: str, asset_name_hex: str, quantity: str, protocol: str,
        wallet_address: Optional[str] = None
    ) -> Optional[LPPosition]:
        """Create an LP position from Blockfrost asset data."""
        try:
            pool_name = None
            lp_value_info = {"ada_value": None, "token_a": {}, "token_b": {}, "apr": None}
            il_data = {}

            # Try to get pool metrics based on protocol
            if protocol == "sundaeswap":
                pool_data = self._get_sundaeswap_pool_metrics(asset_name_hex)
                if pool_data:
                    lp_value_info = self._calculate_sundaeswap_lp_value(quantity, pool_data)
                    # Build pool name from asset tickers (normalized)
                    asset_a = pool_data.get("assetA", {})
                    asset_b = pool_data.get("assetB", {})
                    ticker_a = asset_a.get("ticker", "?")
                    ticker_b = asset_b.get("ticker", "?")
                    if ticker_a and ticker_b and ticker_a != "?" and ticker_b != "?":
                        pool_name = self._normalize_pool_name(ticker_a, ticker_b)

            elif protocol == "minswap":
                pool_metrics = self._get_minswap_pool_metrics(policy_id, asset_name_hex)
                if pool_metrics:
                    lp_value_info = self._calculate_lp_value(quantity, pool_metrics)
                    # Build pool name from asset metadata (normalized)
                    asset_a = pool_metrics.get("asset_a", {}).get("metadata", {})
                    asset_b = pool_metrics.get("asset_b", {}).get("metadata", {})
                    ticker_a = asset_a.get("ticker", "?")
                    ticker_b = asset_b.get("ticker", "?")
                    if ticker_a and ticker_b and ticker_a != "?" and ticker_b != "?":
                        pool_name = self._normalize_pool_name(ticker_a, ticker_b)

            elif protocol == "wingriders":
                pool_data = self._get_wingriders_pool_metrics(policy_id, asset_name_hex)
                if pool_data:
                    lp_value_info = self._calculate_wingriders_lp_value(quantity, pool_data)
                    # Build pool name from token tickers (normalized)
                    token_a = pool_data.get("tokenA", {})
                    token_b = pool_data.get("tokenB", {})
                    ticker_map = pool_data.get("_ticker_map", {})

                    def get_ticker(token):
                        if not token.get("policyId"):
                            return "ADA"
                        key = f"{token.get('policyId', '')}_{token.get('assetName', '')}"
                        return ticker_map.get(key, "?")

                    ticker_a = get_ticker(token_a)
                    ticker_b = get_ticker(token_b)
                    if ticker_a and ticker_b and ticker_a != "?" and ticker_b != "?":
                        pool_name = self._normalize_pool_name(ticker_a, ticker_b)

            # Fall back to Blockfrost metadata for pool name
            if not pool_name:
                pool_name = self._get_pool_name_from_asset(policy_id, asset_name_hex, protocol)

            # Look up APR from database if not available from protocol API
            position_apr = lp_value_info.get("apr")
            if not position_apr and pool_name and pool_name != f"{protocol.upper()} LP":
                position_apr = self._get_pool_apr_from_db(pool_name, protocol)
                if position_apr:
                    logger.debug("Found %s APR from database: %s = %.2f%%", protocol, pool_name, position_apr)

            # Calculate impermanent loss using reserve-based price ratios
            if wallet_address:
                token_a_info = lp_value_info.get("token_a") or {}
                token_b_info = lp_value_info.get("token_b") or {}
                token_a_symbol = token_a_info.get("symbol", "?")
                token_b_symbol = token_b_info.get("symbol", "?")

                logger.info("IL calculation for %s: token_a=%s, token_b=%s", pool_name, token_a_symbol, token_b_symbol)

                if token_a_symbol != "?" and token_b_symbol != "?":
                    # Calculate current price ratio from reserves
                    current_ratio = self._calculate_current_price_ratio(lp_value_info)
                    if current_ratio:
                        il_data["current_price_ratio"] = round(current_ratio, 6)

                    # Check if we have stored entry data
                    stored_entry = self._get_lp_entry_from_db(
                        wallet_address, policy_id, asset_name_hex
                    )
                    logger.info("DB lookup for %s: stored_entry=%s, current_ratio=%s", pool_name, stored_entry, current_ratio)

                    if stored_entry and stored_entry.get("entry_price_ratio"):
                        # Use stored entry data
                        il_data["entry_date"] = stored_entry["entry_date"]
                        il_data["entry_price_ratio"] = stored_entry["entry_price_ratio"]

                        # Calculate IL from ratios
                        if current_ratio:
                            il_result = self._calculate_il_from_ratios(
                                stored_entry["entry_price_ratio"],
                                current_ratio,
                                lp_value_info.get("ada_value")
                            )
                            il_data.update(il_result)
                            logger.info(
                                "Calculated IL for %s: %.2f%% (entry: %s, ratio: %.4f -> %.4f)",
                                pool_name, il_result.get("il_percent", 0),
                                stored_entry["entry_date"],
                                stored_entry["entry_price_ratio"], current_ratio
                            )
                    else:
                        # First time seeing this position - get entry date and store
                        logger.info("No stored entry for %s, fetching creation date...", pool_name)
                        entry_date = self._get_lp_token_creation_date(
                            wallet_address, policy_id, asset_name_hex
                        )
                        logger.info("Got entry_date=%s for %s", entry_date, pool_name)

                        if entry_date and current_ratio:
                            # Store the current ratio as entry ratio (best we can do)
                            # This will be accurate for new positions
                            self._store_lp_entry(
                                wallet_address=wallet_address,
                                policy_id=policy_id,
                                asset_name=asset_name_hex,
                                protocol=protocol,
                                pool_name=pool_name or f"{protocol.upper()} LP",
                                entry_date=entry_date,
                                entry_price_ratio=current_ratio,
                                token_a_symbol=token_a_symbol,
                                token_b_symbol=token_b_symbol,
                            )
                            il_data["entry_date"] = entry_date
                            il_data["entry_price_ratio"] = round(current_ratio, 6)
                            # IL is 0% for newly stored positions
                            il_data["il_percent"] = 0.0
                            logger.info(
                                "Stored new LP entry for %s: date=%s, ratio=%.4f",
                                pool_name, entry_date, current_ratio
                            )

            logger.info("Final il_data for %s: %s", pool_name, il_data)
            return LPPosition(
                protocol=protocol,
                pool=pool_name or f"{protocol.upper()} LP",
                lp_amount=quantity,
                token_a=lp_value_info.get("token_a") or {"symbol": "?", "amount": 0},
                token_b=lp_value_info.get("token_b") or {"symbol": "?", "amount": 0},
                usd_value=lp_value_info.get("ada_value"),
                current_apr=position_apr,
                pool_share_percent=lp_value_info.get("pool_share_percent"),
                entry_date=il_data.get("entry_date"),
                entry_price_ratio=il_data.get("entry_price_ratio"),
                current_price_ratio=il_data.get("current_price_ratio"),
                il_percent=il_data.get("il_percent"),
                il_usd=il_data.get("il_usd"),
            )
        except Exception as e:
            logger.warning("Error creating LP position: %s", e)
            return None

    def _get_pool_name_from_asset(self, policy_id: str, asset_name_hex: str, protocol: str) -> Optional[str]:
        """Try to get a human-readable pool name from the asset."""
        try:
            # Query Blockfrost for asset metadata
            headers = {"project_id": BLOCKFROST_API_KEY}
            asset_id = f"{policy_id}{asset_name_hex}"
            url = f"{BLOCKFROST_API_URL}/assets/{asset_id}"

            resp = self.session.get(url, headers=headers, timeout=self.timeout)

            if resp.status_code == 200:
                data = resp.json()
                # Try to get readable name from metadata
                metadata = data.get("onchain_metadata") or data.get("metadata") or {}

                if isinstance(metadata, dict):
                    name = metadata.get("name") or metadata.get("ticker")
                    if name:
                        return str(name)

                # Fall back to asset_name if it's readable ASCII
                asset_name = data.get("asset_name")
                if asset_name:
                    try:
                        decoded = bytes.fromhex(asset_name).decode('utf-8', errors='strict')
                        # Only use if it's printable ASCII
                        if decoded and len(decoded) > 2 and decoded.isprintable():
                            return decoded
                    except Exception:
                        pass

                # Use fingerprint as a short identifier
                fingerprint = data.get("fingerprint")
                if fingerprint:
                    return f"LP Pool ({fingerprint[:12]}...)"

        except Exception as e:
            logger.debug("Could not fetch asset metadata: %s", e)

        return None

    def get_farm_positions(self, wallet_address: str) -> List[FarmPosition]:
        """
        Fetch staked LP positions from yield farms.

        Checks:
        1. WingRiders farm positions via userShareLocks API
        2. SundaeSwap yield farming API for staked positions
        3. Transaction analysis for other protocol farm contracts

        Args:
            wallet_address: Cardano wallet address

        Returns:
            List of FarmPosition objects
        """
        positions = []

        # Fetch WingRiders farm positions (direct API)
        wingriders_positions = self._fetch_wingriders_farm_positions(wallet_address)
        positions.extend(wingriders_positions)

        # Fetch SundaeSwap yield farming positions (direct API)
        sundae_positions = self._fetch_sundaeswap_yield_positions(wallet_address)
        positions.extend(sundae_positions)

        # Fetch other protocol farm positions via transaction analysis
        if BLOCKFROST_API_KEY:
            other_positions = self._fetch_staked_farm_positions(wallet_address)
            positions.extend(other_positions)
        else:
            logger.warning("BLOCKFROST_API_KEY not configured. Cannot fetch other farm positions.")

        return positions

    def _fetch_wingriders_farm_positions(self, wallet_address: str) -> List[FarmPosition]:
        """
        Fetch staked LP positions from WingRiders farming via userShareLocks API.

        WingRiders farming allows users to lock their LP tokens in farm contracts
        for additional yield rewards. The userShareLocks query returns all locked
        LP positions for a given payment key hash.

        Args:
            wallet_address: Cardano wallet address (bech32 format)

        Returns:
            List of FarmPosition objects for WingRiders staked LPs
        """
        positions = []

        # Extract payment key hash from address
        payment_key = self._extract_payment_key_hash(wallet_address)
        if not payment_key:
            logger.debug("Could not extract payment key for WingRiders farm lookup")
            return positions

        query = """
        query GetUserShareLocks($input: UserShareLocksInput!) {
          userShareLocks(input: $input) {
            txHash
            address
            coins
            outputIndex
            version
            tokenBundle {
              policyId
              assetName
              quantity
            }
          }
        }
        """

        try:
            payload = {
                "query": query,
                "variables": {
                    "input": {
                        "ownerPubKeyHash": payment_key
                    }
                }
            }

            resp = self.session.post(
                WINGRIDERS_API_URL,
                json=payload,
                timeout=self.timeout
            )

            if resp.status_code != 200:
                logger.debug("WingRiders userShareLocks query failed: %d", resp.status_code)
                return positions

            data = resp.json()

            if "errors" in data and data["errors"]:
                logger.debug("WingRiders GraphQL errors: %s", data.get("errors"))
                return positions

            share_locks = data.get("data", {}).get("userShareLocks", [])

            for lock in share_locks:
                # Find LP token in token bundle
                for token in lock.get("tokenBundle", []):
                    policy_id = token.get("policyId", "")
                    asset_name_hex = token.get("assetName", "")
                    quantity = token.get("quantity", "0")

                    # Check if this is a WingRiders LP token
                    if policy_id in LP_POLICY_IDS and LP_POLICY_IDS[policy_id] == "wingriders":
                        # Get pool data for this LP token
                        pool_data = self._get_wingriders_pool_metrics(policy_id, asset_name_hex)
                        lp_value_info = {"ada_value": None, "token_a": {}, "token_b": {}, "apr": None, "pool_share_percent": None}
                        pool_name = "WingRiders LP"

                        if pool_data:
                            lp_value_info = self._calculate_wingriders_lp_value(quantity, pool_data)

                            # Build pool name from token tickers (normalized)
                            token_a = pool_data.get("tokenA", {})
                            token_b = pool_data.get("tokenB", {})
                            ticker_map = pool_data.get("_ticker_map", {})

                            def get_ticker(tok):
                                if not tok.get("policyId"):
                                    return "ADA"
                                key = f"{tok.get('policyId', '')}_{tok.get('assetName', '')}"
                                return ticker_map.get(key, "?")

                            ticker_a = get_ticker(token_a)
                            ticker_b = get_ticker(token_b)
                            if ticker_a and ticker_b and ticker_a != "?" and ticker_b != "?":
                                pool_name = self._normalize_pool_name(ticker_a, ticker_b)

                            # Fetch farm APR (separate from pool APR)
                            farm_apr = self._get_wingriders_farm_apr(policy_id, asset_name_hex)
                            if farm_apr is not None:
                                # Farm APR replaces base APR for staked positions
                                lp_value_info["apr"] = farm_apr

                        # Calculate IL for farm position
                        il_data = self._calculate_farm_position_il(
                            wallet_address, policy_id, asset_name_hex,
                            "wingriders", pool_name, lp_value_info
                        )

                        position = FarmPosition(
                            protocol="wingriders",
                            pool=pool_name,
                            lp_amount=quantity,
                            farm_type="yield_farming",
                            token_a=lp_value_info.get("token_a") or {"symbol": "?", "amount": 0},
                            token_b=lp_value_info.get("token_b") or {"symbol": "?", "amount": 0},
                            usd_value=lp_value_info.get("ada_value"),
                            current_apr=lp_value_info.get("apr"),
                            pool_share_percent=lp_value_info.get("pool_share_percent"),
                            entry_date=il_data.get("entry_date"),
                            entry_price_ratio=il_data.get("entry_price_ratio"),
                            current_price_ratio=il_data.get("current_price_ratio"),
                            il_percent=il_data.get("il_percent"),
                            il_usd=il_data.get("il_usd"),
                        )
                        positions.append(position)
                        logger.debug(
                            "Found WingRiders farm position: %s, LP=%s, value=%s ADA",
                            pool_name, quantity, lp_value_info.get("ada_value")
                        )

            logger.info("Found %d WingRiders farm positions", len(positions))

        except requests.RequestException as e:
            logger.warning("Error fetching WingRiders farm positions: %s", e)
        except Exception as e:
            logger.error("Unexpected error fetching WingRiders farms: %s", e)

        return positions

    def _get_wingriders_farm_apr(self, policy_id: str, asset_name_hex: str) -> Optional[float]:
        """
        Fetch farm APR for a WingRiders LP token.

        Returns the total APR including fees, staking, and farm rewards.
        """
        cache_key = f"wr_farm_apr_{policy_id}_{asset_name_hex}"
        if cache_key in self._pool_metrics_cache:
            return self._pool_metrics_cache[cache_key]

        try:
            # Query active farm by pool asset
            query = """
            query GetFarm($poolAsset: AssetInput!) {
              activeFarmById(poolAsset: $poolAsset) {
                poolId
                yieldAPR(timeframe: CURRENT_EPOCH) {
                  regular { apr }
                  boosting { apr }
                }
                liquidityPool {
                  ... on LiquidityPoolV1 {
                    feesAPR
                    stakingAPR(timeframe: CURRENT_EPOCH)
                  }
                  ... on LiquidityPoolV2 {
                    feesAPR
                    stakingAPR(timeframe: CURRENT_EPOCH)
                  }
                }
              }
            }
            """

            variables = {
                "poolAsset": {
                    "policyId": policy_id,
                    "assetName": asset_name_hex,
                }
            }

            resp = self.session.post(
                WINGRIDERS_API_URL,
                json={"query": query, "variables": variables},
                timeout=self.timeout
            )

            if resp.status_code != 200:
                return None

            data = resp.json()
            farm = data.get("data", {}).get("activeFarmById")

            if not farm:
                return None

            # Calculate total APR
            yield_apr = farm.get("yieldAPR") or {}
            regular = yield_apr.get("regular") or {}
            boosting = yield_apr.get("boosting") or {}
            pool = farm.get("liquidityPool") or {}

            fees_apr = float(pool.get("feesAPR") or 0)
            staking_apr = float(pool.get("stakingAPR") or 0)
            farm_apr = float(regular.get("apr") or 0)
            boost_apr = float(boosting.get("apr") or 0)

            total_apr = fees_apr + staking_apr + farm_apr + boost_apr

            self._pool_metrics_cache[cache_key] = round(total_apr, 2)
            return round(total_apr, 2)

        except Exception as e:
            logger.debug("Error fetching WingRiders farm APR: %s", e)
            return None

    def _fetch_sundaeswap_yield_positions(self, wallet_address: str) -> List[FarmPosition]:
        """
        Fetch staked LP positions from SundaeSwap yield farming API.

        Args:
            wallet_address: Cardano wallet address (bech32 format)

        Returns:
            List of FarmPosition objects for SundaeSwap staked LPs
        """
        positions = []

        query = """
        {
          positions(beneficiary: "%s") {
            txHash
            index
            spentTxHash
            value { assetID amount }
            delegation {
              pool {
                poolIdent
                lpAsset
                assetA
                assetB
              }
              program { id label }
            }
          }
        }
        """ % wallet_address

        try:
            resp = self.session.post(
                SUNDAESWAP_YIELD_API_URL,
                json={"query": query},
                timeout=self.timeout
            )

            if resp.status_code != 200:
                logger.debug("SundaeSwap yield API error: %d", resp.status_code)
                return positions

            data = resp.json()

            if "errors" in data:
                logger.debug("SundaeSwap yield API GraphQL errors: %s", data["errors"])
                return positions

            api_positions = data.get("data", {}).get("positions", [])

            # Filter to only active (unspent) positions
            active_positions = [p for p in api_positions if not p.get("spentTxHash")]

            for pos in active_positions:
                # Find LP token in value array
                lp_asset_id = None
                lp_amount = None

                for value in pos.get("value", []):
                    asset_id = value.get("assetID", "")
                    # Skip ADA
                    if asset_id == "ada.lovelace":
                        continue
                    # Check if this is a SundaeSwap LP token
                    if asset_id.startswith(SUNDAESWAP_V3_LP_POLICY):
                        lp_asset_id = asset_id
                        lp_amount = value.get("amount")
                        break

                if not lp_asset_id or not lp_amount:
                    continue

                # Extract asset name hex from asset ID (policy.assetname format)
                parts = lp_asset_id.split(".")
                if len(parts) != 2:
                    continue

                policy_id = parts[0]
                asset_name_hex = parts[1]

                # Get pool metrics for value calculation
                pool_data = self._get_sundaeswap_pool_metrics(asset_name_hex)
                lp_value_info = {"ada_value": None, "token_a": {}, "token_b": {}, "apr": None}
                pool_name = "SundaeSwap LP"

                if pool_data:
                    lp_value_info = self._calculate_sundaeswap_lp_value(lp_amount, pool_data)
                    # Build pool name from asset tickers (normalized)
                    asset_a = pool_data.get("assetA", {})
                    asset_b = pool_data.get("assetB", {})
                    ticker_a = asset_a.get("ticker", "?")
                    ticker_b = asset_b.get("ticker", "?")
                    if ticker_a and ticker_b and ticker_a != "?" and ticker_b != "?":
                        pool_name = self._normalize_pool_name(ticker_a, ticker_b)

                # Look up APR from database if not available from API
                farm_apr = lp_value_info.get("apr")
                if not farm_apr and pool_name != "SundaeSwap LP":
                    farm_apr = self._get_pool_apr_from_db(pool_name, "sundaeswap")
                    if farm_apr:
                        logger.debug("Found SundaeSwap APR from database: %s = %.2f%%", pool_name, farm_apr)

                # Calculate IL for farm position
                il_data = self._calculate_farm_position_il(
                    wallet_address, policy_id, asset_name_hex,
                    "sundaeswap", pool_name, lp_value_info
                )

                position = FarmPosition(
                    protocol="sundaeswap",
                    pool=pool_name,
                    lp_amount=lp_amount,
                    farm_type="yield_farming",
                    token_a=lp_value_info.get("token_a") or {"symbol": "?", "amount": 0},
                    token_b=lp_value_info.get("token_b") or {"symbol": "?", "amount": 0},
                    usd_value=lp_value_info.get("ada_value"),
                    current_apr=farm_apr,
                    rewards_earned=None,
                    pool_share_percent=lp_value_info.get("pool_share_percent"),
                    entry_date=il_data.get("entry_date"),
                    entry_price_ratio=il_data.get("entry_price_ratio"),
                    current_price_ratio=il_data.get("current_price_ratio"),
                    il_percent=il_data.get("il_percent"),
                    il_usd=il_data.get("il_usd"),
                )
                positions.append(position)

            logger.info("Found %d SundaeSwap yield farming positions", len(positions))

        except requests.RequestException as e:
            logger.warning("Error fetching SundaeSwap yield positions: %s", e)
        except Exception as e:
            logger.error("Unexpected error fetching SundaeSwap yield positions: %s", e)

        return positions

    def _fetch_staked_farm_positions(self, wallet_address: str) -> List[FarmPosition]:
        """
        Fetch staked LP positions by analyzing recent transactions.

        Since staked LP tokens are held in DEX farm contracts (not user addresses),
        we detect them by looking at recent transactions where LP tokens were sent
        to known farm contract addresses.
        """
        positions = []
        headers = {"project_id": BLOCKFROST_API_KEY}

        # Known farm contract addresses
        FARM_CONTRACTS = {
            "addr1wxc45xspppp73takl93mq029905ptdfnmtgv6g7cr8pdyqgvks3s8": "minswap",
            # Add more farm contracts as discovered
        }

        try:
            # Get recent transactions for the wallet
            url = f"{BLOCKFROST_API_URL}/addresses/{wallet_address}/transactions"
            params = {"count": 20, "order": "desc"}
            resp = self.session.get(url, headers=headers, params=params, timeout=self.timeout)

            if resp.status_code != 200:
                logger.debug("Could not fetch transactions: %d", resp.status_code)
                return positions

            transactions = resp.json()

            # Track LP tokens sent to farm contracts
            staked_lp = {}  # {asset_id: {amount, protocol, tx_hash}}

            for tx_info in transactions:
                tx_hash = tx_info.get("tx_hash", "")

                # Get transaction UTXOs
                url = f"{BLOCKFROST_API_URL}/txs/{tx_hash}/utxos"
                resp = self.session.get(url, headers=headers, timeout=self.timeout)

                if resp.status_code != 200:
                    continue

                tx_data = resp.json()

                # Check outputs going to farm contracts
                for output in tx_data.get("outputs", []):
                    output_addr = output.get("address", "")

                    if output_addr in FARM_CONTRACTS:
                        farm_protocol = FARM_CONTRACTS[output_addr]

                        for asset in output.get("amount", []):
                            unit = asset.get("unit", "")
                            quantity = asset.get("quantity", "0")

                            if unit == "lovelace":
                                continue

                            if len(unit) >= 56:
                                policy_id = unit[:56]

                                if policy_id in LP_POLICY_IDS:
                                    # This is an LP token sent to a farm
                                    lp_protocol = LP_POLICY_IDS[policy_id]
                                    asset_name_hex = unit[56:]

                                    # Only track if it came from user's wallet
                                    from_user = any(
                                        inp.get("address", "").startswith(wallet_address[:30])
                                        for inp in tx_data.get("inputs", [])
                                    )

                                    if from_user:
                                        if unit not in staked_lp:
                                            staked_lp[unit] = {
                                                "amount": quantity,
                                                "protocol": lp_protocol,
                                                "policy_id": policy_id,
                                                "asset_name_hex": asset_name_hex,
                                                "tx_hash": tx_hash,
                                            }

                # Also check if LP tokens were withdrawn (sent back to user)
                for output in tx_data.get("outputs", []):
                    output_addr = output.get("address", "")

                    if output_addr.startswith(wallet_address[:30]):
                        for asset in output.get("amount", []):
                            unit = asset.get("unit", "")

                            # If LP token came back to wallet, remove from staked
                            if unit in staked_lp:
                                # Check if input was from farm
                                from_farm = any(
                                    inp.get("address", "") in FARM_CONTRACTS
                                    for inp in tx_data.get("inputs", [])
                                )
                                if from_farm:
                                    del staked_lp[unit]

            # Create farm positions from staked LP tokens
            for unit, lp_info in staked_lp.items():
                pool_name = self._get_pool_name_from_asset(
                    lp_info["policy_id"],
                    lp_info["asset_name_hex"],
                    lp_info["protocol"]
                )

                # Try to get pool metrics for value calculation
                lp_value_info = {"ada_value": None, "token_a": {}, "token_b": {}, "apr": None}

                if lp_info["protocol"] == "minswap":
                    pool_metrics = self._get_minswap_pool_metrics(
                        lp_info["policy_id"],
                        lp_info["asset_name_hex"]
                    )
                    if pool_metrics:
                        lp_value_info = self._calculate_lp_value(lp_info["amount"], pool_metrics)
                        # Use pool name from metrics if available (normalized)
                        asset_a = pool_metrics.get("asset_a", {}).get("metadata", {})
                        asset_b = pool_metrics.get("asset_b", {}).get("metadata", {})
                        ticker_a = asset_a.get("ticker", "?")
                        ticker_b = asset_b.get("ticker", "?")
                        if ticker_a and ticker_b and ticker_a != "?" and ticker_b != "?":
                            pool_name = self._normalize_pool_name(ticker_a, ticker_b)

                elif lp_info["protocol"] == "sundaeswap":
                    pool_data = self._get_sundaeswap_pool_metrics(lp_info["asset_name_hex"])
                    if pool_data:
                        lp_value_info = self._calculate_sundaeswap_lp_value(
                            lp_info["amount"], pool_data
                        )
                        # Use pool name from API (normalized)
                        asset_a = pool_data.get("assetA", {})
                        asset_b = pool_data.get("assetB", {})
                        ticker_a = asset_a.get("ticker", "?")
                        ticker_b = asset_b.get("ticker", "?")
                        if ticker_a and ticker_b and ticker_a != "?" and ticker_b != "?":
                            pool_name = self._normalize_pool_name(ticker_a, ticker_b)

                elif lp_info["protocol"] == "wingriders":
                    pool_data = self._get_wingriders_pool_metrics(
                        lp_info["policy_id"], lp_info["asset_name_hex"]
                    )
                    if pool_data:
                        lp_value_info = self._calculate_wingriders_lp_value(
                            lp_info["amount"], pool_data
                        )
                        # Use pool name from API (normalized)
                        token_a = pool_data.get("tokenA", {})
                        token_b = pool_data.get("tokenB", {})
                        ticker_map = pool_data.get("_ticker_map", {})

                        def get_ticker(token):
                            if not token.get("policyId"):
                                return "ADA"
                            key = f"{token.get('policyId', '')}_{token.get('assetName', '')}"
                            return ticker_map.get(key, "?")

                        ticker_a = get_ticker(token_a)
                        ticker_b = get_ticker(token_b)
                        if ticker_a and ticker_b and ticker_a != "?" and ticker_b != "?":
                            pool_name = self._normalize_pool_name(ticker_a, ticker_b)

                # Look up APR from database if not available from protocol API
                farm_apr = lp_value_info.get("apr")
                if not farm_apr and pool_name and pool_name != f"{lp_info['protocol'].upper()} LP":
                    farm_apr = self._get_pool_apr_from_db(pool_name, lp_info["protocol"])
                    if farm_apr:
                        logger.debug("Found %s farm APR from database: %s = %.2f%%",
                                     lp_info["protocol"], pool_name, farm_apr)

                # Calculate IL for farm position
                final_pool_name = pool_name or f"{lp_info['protocol'].upper()} LP"
                il_data = self._calculate_farm_position_il(
                    wallet_address, lp_info["policy_id"], lp_info["asset_name_hex"],
                    lp_info["protocol"], final_pool_name, lp_value_info
                )

                position = FarmPosition(
                    protocol=lp_info["protocol"],
                    pool=final_pool_name,
                    lp_amount=lp_info["amount"],
                    farm_type="yield_farming",
                    token_a=lp_value_info.get("token_a") or {"symbol": "?", "amount": 0},
                    token_b=lp_value_info.get("token_b") or {"symbol": "?", "amount": 0},
                    usd_value=lp_value_info.get("ada_value"),  # ADA value for now
                    current_apr=farm_apr,
                    rewards_earned=None,
                    pool_share_percent=lp_value_info.get("pool_share_percent"),
                    entry_date=il_data.get("entry_date"),
                    entry_price_ratio=il_data.get("entry_price_ratio"),
                    current_price_ratio=il_data.get("current_price_ratio"),
                    il_percent=il_data.get("il_percent"),
                    il_usd=il_data.get("il_usd"),
                )
                positions.append(position)

            logger.info("Found %d farm positions from transaction analysis", len(positions))

        except requests.RequestException as e:
            logger.warning("Error fetching farm positions: %s", e)
        except Exception as e:
            logger.error("Unexpected error fetching farm positions: %s", e)

        return positions

    def _check_address_for_lp_tokens(self, address: str, is_farm: bool = False) -> List[FarmPosition]:
        """Check an address for LP tokens and return farm positions."""
        positions = []
        headers = {"project_id": BLOCKFROST_API_KEY}

        try:
            # Get UTXOs at this address
            url = f"{BLOCKFROST_API_URL}/addresses/{address}/utxos"
            resp = self.session.get(url, headers=headers, timeout=self.timeout)

            if resp.status_code == 404:
                return positions

            if resp.status_code != 200:
                logger.debug("Could not fetch UTXOs for %s: %d", address[:20], resp.status_code)
                return positions

            utxos = resp.json()

            for utxo in utxos:
                amounts = utxo.get("amount", [])

                for asset in amounts:
                    unit = asset.get("unit", "")
                    quantity = asset.get("quantity", "0")

                    if unit == "lovelace":
                        continue

                    if len(unit) >= 56:
                        policy_id = unit[:56]
                        asset_name_hex = unit[56:]

                        if policy_id in LP_POLICY_IDS:
                            protocol = LP_POLICY_IDS[policy_id]
                            pool_name = self._get_pool_name_from_asset(policy_id, asset_name_hex, protocol)

                            position = FarmPosition(
                                protocol=protocol,
                                pool=pool_name or f"{protocol.upper()} LP",
                                lp_amount=quantity,
                                farm_type="yield_farming",
                                token_a={"symbol": "?", "amount": 0},
                                token_b={"symbol": "?", "amount": 0},
                                usd_value=None,
                                current_apr=None,
                                rewards_earned=None,
                            )
                            positions.append(position)

        except Exception as e:
            logger.debug("Error checking address %s for LP tokens: %s", address[:20], e)

        return positions

    def get_lending_positions(self, wallet_address: str) -> List[LendingPosition]:
        """
        Fetch lending positions from Liqwid.

        Args:
            wallet_address: Cardano wallet address

        Returns:
            List of LendingPosition objects
        """
        return self._fetch_liqwid_positions(wallet_address)

    def _fetch_liqwid_positions(self, wallet_address: str) -> List[LendingPosition]:
        """Fetch lending/borrowing positions from Liqwid Finance.

        Supply positions are detected by scanning wallet for qTokens (receipt tokens).
        Borrow positions are fetched via the Liqwid loans API using payment key.
        """
        positions = []

        # Fetch supply positions by detecting qTokens in wallet
        supply_positions = self._fetch_liqwid_supply_positions(wallet_address)
        positions.extend(supply_positions)

        # Fetch borrow positions via Liqwid loans API
        borrow_positions = self._fetch_liqwid_borrow_positions(wallet_address)
        positions.extend(borrow_positions)

        return positions

    def _extract_payment_key_hash(self, wallet_address: str) -> Optional[str]:
        """Extract payment key hash from Cardano bech32 address."""
        try:
            # Bech32 decoding
            BECH32_CHARSET = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l'

            bech = wallet_address.lower()
            pos = bech.rfind('1')
            if pos < 1:
                return None

            data = [BECH32_CHARSET.find(c) for c in bech[pos + 1:]]

            # Convert from 5-bit to 8-bit (remove checksum)
            acc = 0
            bits = 0
            decoded = []
            for value in data[:-6]:  # Remove 6 checksum chars
                acc = (acc << 5) | value
                bits += 5
                while bits >= 8:
                    bits -= 8
                    decoded.append((acc >> bits) & 0xff)

            # First byte is header, bytes 1-28 are payment key hash
            if len(decoded) >= 29:
                payment_key_hash = bytes(decoded[1:29]).hex()
                return payment_key_hash

        except Exception as e:
            logger.debug("Error extracting payment key hash: %s", e)

        return None

    def _fetch_liqwid_supply_positions(self, wallet_address: str) -> List[LendingPosition]:
        """Fetch supply positions by detecting qTokens in wallet via Blockfrost."""
        positions = []

        if not BLOCKFROST_API_KEY:
            logger.debug("Blockfrost API key not configured, skipping Liqwid supply detection")
            return positions

        try:
            # Get wallet assets from Blockfrost
            headers = {"project_id": BLOCKFROST_API_KEY}
            url = f"{BLOCKFROST_API_URL}/addresses/{wallet_address}"
            resp = self.session.get(url, headers=headers, timeout=self.timeout)

            if resp.status_code != 200:
                logger.debug("Failed to fetch wallet address: %d", resp.status_code)
                return positions

            address_data = resp.json()

            # Check each asset for qToken policy IDs
            for asset in address_data.get("amount", []):
                unit = asset.get("unit", "")
                quantity = asset.get("quantity", "0")

                if unit == "lovelace" or len(unit) < 56:
                    continue

                policy_id = unit[:56]

                if policy_id in LIQWID_QTOKEN_POLICY_IDS:
                    market_id = LIQWID_QTOKEN_POLICY_IDS[policy_id]

                    # Fetch market data for exchange rate and APY
                    market_data = self._get_liqwid_market_data(market_id)
                    if market_data:
                        position = self._create_liqwid_supply_position(
                            market_id, market_data, quantity
                        )
                        if position:
                            positions.append(position)
                            logger.debug(
                                "Found Liqwid supply: %s, qTokens=%s",
                                market_data.get("symbol"), quantity
                            )

        except requests.RequestException as e:
            logger.warning("Error fetching Liqwid supply positions: %s", e)
        except Exception as e:
            logger.error("Unexpected error fetching Liqwid supplies: %s", e)

        return positions

    def _fetch_liqwid_borrow_positions(self, wallet_address: str) -> List[LendingPosition]:
        """Fetch borrow positions via Liqwid loans API."""
        positions = []

        # Extract payment key hash from address
        payment_key = self._extract_payment_key_hash(wallet_address)
        if not payment_key:
            logger.debug("Could not extract payment key from address")
            return positions

        query = """
        query GetLoans($paymentKeys: [String!]) {
            liqwid {
                data {
                    loans(input: { paymentKeys: $paymentKeys }) {
                        results {
                            id
                            amount
                            adjustedAmount
                            collateral
                            healthFactor
                            LTV
                            APY
                            market {
                                id
                                symbol
                                borrowAPY
                            }
                            asset {
                                symbol
                                decimals
                                price
                            }
                        }
                    }
                }
            }
        }
        """

        try:
            payload = {
                "query": query,
                "variables": {"paymentKeys": [payment_key]},
            }

            resp = self.session.post(
                LIQWID_API_URL,
                json=payload,
                timeout=self.timeout,
            )

            if resp.status_code != 200:
                logger.debug("Liqwid loans query failed: %d", resp.status_code)
                return positions

            data = resp.json()

            if "errors" in data:
                logger.debug("Liqwid GraphQL errors: %s", data.get("errors"))
                return positions

            loans = (
                data.get("data", {})
                .get("liqwid", {})
                .get("data", {})
                .get("loans", {})
                .get("results", [])
            )

            for loan in loans:
                position = self._parse_liqwid_loan(loan)
                if position:
                    positions.append(position)

            logger.info("Found %d Liqwid borrow positions", len(positions))

        except requests.RequestException as e:
            logger.warning("Error fetching Liqwid borrow positions: %s", e)
        except Exception as e:
            logger.error("Unexpected error fetching Liqwid borrows: %s", e)

        return positions

    def _get_liqwid_market_data(self, market_id: str) -> Optional[Dict]:
        """Fetch market data from Liqwid API for a given market ID."""
        cache_key = f"liqwid_market_{market_id}"
        if cache_key in self._pool_metrics_cache:
            return self._pool_metrics_cache[cache_key]

        query = """
        query GetMarket($id: String!) {
            liqwid {
                data {
                    market(input: { id: $id }) {
                        id
                        symbol
                        displayName
                        exchangeRate
                        supplyAPY
                        borrowAPY
                        asset {
                            decimals
                            price
                        }
                    }
                }
            }
        }
        """

        try:
            payload = {
                "query": query,
                "variables": {"id": market_id},
            }

            resp = self.session.post(
                LIQWID_API_URL,
                json=payload,
                timeout=self.timeout,
            )

            if resp.status_code == 200:
                data = resp.json()
                market = (
                    data.get("data", {})
                    .get("liqwid", {})
                    .get("data", {})
                    .get("market")
                )
                if market:
                    self._pool_metrics_cache[cache_key] = market
                    return market

        except Exception as e:
            logger.debug("Error fetching Liqwid market %s: %s", market_id, e)

        return None

    def _create_liqwid_supply_position(
        self, market_id: str, market_data: Dict, qtoken_amount: str
    ) -> Optional[LendingPosition]:
        """Create a LendingPosition from qToken balance and market data."""
        try:
            symbol = market_data.get("symbol", market_id)
            exchange_rate = float(market_data.get("exchangeRate", 0))
            supply_apy = float(market_data.get("supplyAPY", 0))

            # qTokens have 6 decimals
            qtoken_balance = int(qtoken_amount) / 1_000_000

            # Underlying amount = qToken balance * exchange rate
            # Exchange rate represents how much underlying you get per qToken
            # (e.g., rate of 0.02 means 1 qToken = 0.02 underlying)
            underlying_amount = qtoken_balance * exchange_rate

            if underlying_amount <= 0:
                return None

            # Calculate USD value
            asset_data = market_data.get("asset", {})
            price = float(asset_data.get("price", 0))
            usd_value = underlying_amount * price if price > 0 else None

            # Convert APY to percentage
            apy_percent = supply_apy * 100

            return LendingPosition(
                protocol="liqwid",
                market=symbol,
                position_type="supply",
                amount=round(underlying_amount, 6),
                usd_value=round(usd_value, 2) if usd_value else None,
                current_apy=round(apy_percent, 2) if apy_percent > 0 else None,
            )

        except Exception as e:
            logger.warning("Error creating Liqwid supply position: %s", e)
            return None

    def _parse_liqwid_loan(self, loan: Dict) -> Optional[LendingPosition]:
        """Parse a Liqwid loan (borrow position)."""
        try:
            market = loan.get("market", {})
            asset = loan.get("asset", {})

            symbol = market.get("symbol") or asset.get("symbol", "?")
            amount = float(loan.get("amount", 0))
            borrow_apy = float(loan.get("APY", 0))

            if amount <= 0:
                return None

            # Calculate USD value
            price = float(asset.get("price", 0))
            usd_value = amount * price if price > 0 else None

            # APY from loan is already a decimal
            apy_percent = borrow_apy * 100

            return LendingPosition(
                protocol="liqwid",
                market=symbol,
                position_type="borrow",
                amount=round(amount, 6),
                usd_value=round(usd_value, 2) if usd_value else None,
                current_apy=round(apy_percent, 2) if apy_percent > 0 else None,
            )

        except Exception as e:
            logger.warning("Error parsing Liqwid loan: %s", e)
            return None

