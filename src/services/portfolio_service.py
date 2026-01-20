"""Portfolio service for fetching user DeFi positions.

Fetches LP positions via Blockfrost API and lending positions from Liqwid Finance.
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Blockfrost API configuration (free tier: 50,000 requests/day)
BLOCKFROST_API_URL = "https://cardano-mainnet.blockfrost.io/api/v0"
BLOCKFROST_API_KEY = os.environ.get("BLOCKFROST_API_KEY", "")

# Minswap API for pool data
MINSWAP_API_URL = "https://api-mainnet-prod.minswap.org"

# Known LP token policy IDs for Cardano DEXes
LP_POLICY_IDS = {
    "f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c": "minswap",
    "e4214b7cce62ac6fbba385d164df48e157eae5863521b4b67ca71d86": "sundaeswap",
    "026a18d04a0c642759bb3d83b12e3344894e5c1c7b2aeb1a2113a570": "wingriders",
    "1d7f33bd23d85e1a25d87d86fac4f199c3197a2f7afeb662a0f34e1e": "wingriders",  # WR V2
}


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
        self.liqwid_api = "https://v2.api.liqwid.finance/graphql"

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "defitracker/1.0",
            "Content-Type": "application/json",
        })
        self.timeout = 15

        # Cache for pool metrics data
        self._pool_metrics_cache: Dict[str, Dict] = {}

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
                            policy_id, asset_name_hex, quantity, protocol
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
        self, policy_id: str, asset_name_hex: str, quantity: str, protocol: str
    ) -> Optional[LPPosition]:
        """Create an LP position from Blockfrost asset data."""
        try:
            # Decode asset name from hex to get pool info
            try:
                asset_name = bytes.fromhex(asset_name_hex).decode('utf-8', errors='replace')
            except Exception:
                asset_name = asset_name_hex[:16] + "..."

            # Try to get more details about this LP token from Blockfrost
            pool_name = self._get_pool_name_from_asset(policy_id, asset_name_hex, protocol)

            return LPPosition(
                protocol=protocol,
                pool=pool_name or f"{protocol.upper()} LP",
                lp_amount=quantity,
                token_a={"symbol": "?", "amount": 0},  # Would need pool query to get breakdown
                token_b={"symbol": "?", "amount": 0},
                usd_value=None,  # Would need price feed
                current_apr=None,
                pool_share_percent=None,
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

        Checks all addresses associated with the stake key, including script
        addresses used by DEX yield farming contracts.

        Args:
            wallet_address: Cardano wallet address

        Returns:
            List of FarmPosition objects
        """
        if not BLOCKFROST_API_KEY:
            logger.warning("BLOCKFROST_API_KEY not configured. Cannot fetch farm positions.")
            return []

        return self._fetch_staked_farm_positions(wallet_address)

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

                # Try to get pool metrics for value calculation (Minswap only for now)
                lp_value_info = {"ada_value": None, "token_a": {}, "token_b": {}, "apr": None}
                if lp_info["protocol"] == "minswap":
                    pool_metrics = self._get_minswap_pool_metrics(
                        lp_info["policy_id"],
                        lp_info["asset_name_hex"]
                    )
                    if pool_metrics:
                        lp_value_info = self._calculate_lp_value(lp_info["amount"], pool_metrics)
                        # Use pool name from metrics if available
                        asset_a = pool_metrics.get("asset_a", {}).get("metadata", {})
                        asset_b = pool_metrics.get("asset_b", {}).get("metadata", {})
                        ticker_a = asset_a.get("ticker", "?")
                        ticker_b = asset_b.get("ticker", "?")
                        if ticker_a and ticker_b:
                            pool_name = f"{ticker_a}/{ticker_b}"

                position = FarmPosition(
                    protocol=lp_info["protocol"],
                    pool=pool_name or f"{lp_info['protocol'].upper()} LP",
                    lp_amount=lp_info["amount"],
                    farm_type="yield_farming",
                    token_a=lp_value_info.get("token_a") or {"symbol": "?", "amount": 0},
                    token_b=lp_value_info.get("token_b") or {"symbol": "?", "amount": 0},
                    usd_value=lp_value_info.get("ada_value"),  # ADA value for now
                    current_apr=lp_value_info.get("apr"),
                    rewards_earned=None,
                    pool_share_percent=lp_value_info.get("pool_share_percent"),
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
        """Fetch lending/borrowing positions from Liqwid Finance."""
        positions = []

        query = """
        query UserPositions($address: String!) {
            liqwid {
                data {
                    user(address: $address) {
                        supplies {
                            market {
                                id
                                symbol
                                supplyAPY
                            }
                            qTokenBalance
                            underlyingBalance
                            valueUsd
                        }
                        borrows {
                            market {
                                id
                                symbol
                                borrowAPY
                            }
                            borrowBalance
                            valueUsd
                        }
                        totalSupplyUsd
                        totalBorrowUsd
                    }
                }
            }
        }
        """

        try:
            payload = {
                "query": query,
                "variables": {"address": wallet_address},
            }

            resp = self.session.post(
                self.liqwid_api,
                json=payload,
                timeout=self.timeout,
            )

            if resp.status_code != 200:
                logger.debug("Liqwid positions query failed: %d", resp.status_code)
                return positions

            data = resp.json()

            if "errors" in data:
                logger.debug("Liqwid GraphQL errors: %s", data["errors"])
                return positions

            user_data = (
                data.get("data", {})
                .get("liqwid", {})
                .get("data", {})
                .get("user")
            )

            if not user_data:
                logger.debug("No Liqwid user data for %s", wallet_address[:20])
                return positions

            # Parse supply positions
            for supply in user_data.get("supplies", []):
                position = self._parse_liqwid_supply(supply)
                if position:
                    positions.append(position)

            # Parse borrow positions
            for borrow in user_data.get("borrows", []):
                position = self._parse_liqwid_borrow(borrow)
                if position:
                    positions.append(position)

        except requests.RequestException as e:
            logger.warning("Error fetching Liqwid positions: %s", e)
        except Exception as e:
            logger.error("Unexpected error parsing Liqwid data: %s", e)

        return positions

    def _parse_liqwid_supply(self, data: Dict) -> Optional[LendingPosition]:
        """Parse a Liqwid supply position."""
        try:
            market = data.get("market", {})
            symbol = market.get("symbol", "?")

            # API returns APY as decimal (0.0325 for 3.25%)
            supply_apy = market.get("supplyAPY")
            apy_percent = float(supply_apy) * 100 if supply_apy else None

            amount = float(data.get("underlyingBalance") or 0)

            if amount <= 0:
                return None

            return LendingPosition(
                protocol="liqwid",
                market=symbol,
                position_type="supply",
                amount=amount,
                usd_value=data.get("valueUsd"),
                current_apy=apy_percent,
            )
        except Exception as e:
            logger.warning("Error parsing Liqwid supply: %s", e)
            return None

    def _parse_liqwid_borrow(self, data: Dict) -> Optional[LendingPosition]:
        """Parse a Liqwid borrow position."""
        try:
            market = data.get("market", {})
            symbol = market.get("symbol", "?")

            # API returns APY as decimal
            borrow_apy = market.get("borrowAPY")
            apy_percent = float(borrow_apy) * 100 if borrow_apy else None

            amount = float(data.get("borrowBalance") or 0)

            if amount <= 0:
                return None

            return LendingPosition(
                protocol="liqwid",
                market=symbol,
                position_type="borrow",
                amount=amount,
                usd_value=data.get("valueUsd"),
                current_apy=apy_percent,
            )
        except Exception as e:
            logger.warning("Error parsing Liqwid borrow: %s", e)
            return None
