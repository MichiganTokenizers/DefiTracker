"""Kinetic protocol adapter for Flare blockchain"""
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta
import logging
from web3 import Web3
from eth_utils import keccak, to_bytes, to_hex
from src.adapters.base import ProtocolAdapter
from src.adapters.flare.abi_fetcher import fetch_abi_from_flarescan, get_minimal_lens_abi

logger = logging.getLogger(__name__)


class KineticAdapter(ProtocolAdapter):
    """Adapter for Kinetic protocol on Flare blockchain"""
    
    def __init__(self, protocol_name: str, config: Dict):
        super().__init__(protocol_name, config)
        # FXRP-USDT0-stXRP market tokens (uses Lens)
        self.tokens = config.get('tokens', {})
        self.unitroller = config.get('unitroller')
        self.comptroller = config.get('comptroller')
        self.lens = config.get('lens')  # Lens contract for reading market data
        
        # JOULE-USDC-FLR market tokens (uses direct ISO queries)
        self.joule_market = config.get('joule_market', {})
        self.joule_tokens = self.joule_market.get('tokens', {})
        
        # Merge all tokens into a unified view
        self._all_tokens = {}
        for symbol, token_config in self.tokens.items():
            token_config['market_type'] = 'lens'  # Uses Lens contract
            self._all_tokens[symbol] = token_config
        for symbol, token_config in self.joule_tokens.items():
            token_config['market_type'] = 'direct'  # Uses direct ISO queries
            self._all_tokens[symbol] = token_config
        
        self.web3 = None  # Will be set by chain adapter
        # Store reference to parent config for accessing other protocols (e.g., BlazeSwap)
        self._parent_config = config.get('_parent_config')
        
    def set_web3_instance(self, web3: Web3):
        """Set Web3 instance from chain adapter"""
        self.web3 = web3
    
    def get_supported_assets(self) -> List[str]:
        """
        Get list of supported assets from configuration.
        
        Returns:
            List of asset symbols from all markets (e.g., ['FXRP', 'USDT0', 'stXRP', 'FLR', 'USDC', 'JOULE'])
        """
        return list(self._all_tokens.keys())
    
    def get_supply_apr(self, asset: str) -> Optional[Decimal]:
        """
        Get supply APR from Kinetic protocol (on-chain).
        
        For FXRP market: Uses Lens contract
        For JOULE market: Uses direct ISO contract queries
        
        Args:
            asset: Token symbol (e.g., FXRP, USDT0, stXRP, FLR, USDC, JOULE)
            
        Returns:
            Total APY as Decimal (supply APR + distribution APR), or None if unavailable
        """
        if asset not in self._all_tokens:
            logger.warning(f"Asset {asset} not configured in tokens")
            return None
        
        if not self.web3:
            logger.error("Web3 instance not set. Cannot query contracts.")
            return None
        
        token_config = self._all_tokens[asset]
        market_type = token_config.get('market_type', 'lens')
        
        try:
            if market_type == 'lens':
                apr = self._get_apr_from_lens(asset)
            else:
                apr = self._get_apr_from_direct(asset)
            
            if apr is not None:
                logger.info(f"Retrieved APR for {asset} from {market_type} query: {apr}%")
            return apr
        except Exception as e:
            logger.error(f"Error fetching APR for {asset}: {e}")
            return None
    
    def get_borrow_apr(self, asset: str) -> Optional[Decimal]:
        """
        Get borrow APR from Kinetic protocol (on-chain).
        
        For FXRP market: Uses Lens contract
        For JOULE market: Uses direct ISO contract queries
        
        Args:
            asset: Token symbol (e.g., FXRP, USDT0, stXRP, FLR, USDC, JOULE)
            
        Returns:
            Borrow APR as Decimal (e.g., 9.59 for 9.59%), or None if unavailable
        """
        if asset not in self._all_tokens:
            logger.warning(f"Asset {asset} not configured in tokens")
            return None
        
        if not self.web3:
            logger.error("Web3 instance not set. Cannot query contracts.")
            return None
        
        token_config = self._all_tokens[asset]
        market_type = token_config.get('market_type', 'lens')
        
        try:
            if market_type == 'lens':
                borrow_apr = self._get_borrow_apr_from_lens(asset)
            else:
                borrow_apr = self._get_borrow_apr_from_direct(asset)
            
            if borrow_apr is not None:
                logger.info(f"Retrieved borrow APR for {asset} from {market_type} query: {borrow_apr}%")
            return borrow_apr
        except Exception as e:
            logger.error(f"Error fetching borrow APR for {asset}: {e}")
            return None
    
    def get_supply_apr_breakdown(self, asset: str) -> Optional[Dict[str, Decimal]]:
        """
        Get supply APR breakdown: supply APR and distribution APR separately.
        
        For FXRP market: Uses Lens contract (includes distribution rewards)
        For JOULE market: Uses direct ISO contract queries (base rates only, no distribution yet)
        
        Args:
            asset: Token symbol (e.g., FXRP, USDT0, stXRP, FLR, USDC, JOULE)
            
        Returns:
            Dict with keys: 'supply_apr', 'distribution_apr', 'total_apy'
            or None if unavailable
        """
        if asset not in self._all_tokens:
            logger.warning(f"Asset {asset} not configured in tokens")
            return None
        
        if not self.web3:
            logger.error("Web3 instance not set. Cannot query contracts.")
            return None
        
        token_config = self._all_tokens[asset]
        market_type = token_config.get('market_type', 'lens')
        
        try:
            if market_type == 'lens':
                breakdown = self._get_supply_apr_breakdown_from_lens(asset)
            else:
                breakdown = self._get_supply_apr_breakdown_from_direct(asset)
            return breakdown
        except Exception as e:
            logger.error(f"Error fetching supply APR breakdown for {asset}: {e}")
            return None
    
    def compute_apr_from_onchain(
        self, 
        asset: str, 
        lookback_days: int = 7
    ) -> Optional[Decimal]:
        """
        Method 2: Compute APR from on-chain data.
        
        Calculates APR by:
        1. Aggregating rewards paid for the token over the period
        2. Aggregating total volume supplied for the token
        3. Applying formula: APR = (rewards / volume) × (365 / days) × 100
        
        Args:
            asset: Token symbol (e.g., FXRP, USDT0, stXRP)
            lookback_days: Number of days to look back (default 7)
            
        Returns:
            APR as Decimal, or None if computation fails
        """
        if asset not in self.tokens:
            logger.warning(f"Asset {asset} not configured in tokens")
            return None
        
        if not self.web3:
            logger.error("Web3 instance not set. Cannot compute APR from on-chain data.")
            return None
        
        try:
            # Get token and ISO market addresses
            token_config = self.tokens.get(asset)
            if not token_config:
                logger.error(f"Token config not found for {asset}")
                return None
            
            token_address = token_config.get('address')
            iso_address = token_config.get('iso_address')
            if not token_address or not iso_address:
                logger.error(f"Token or ISO address not found for {asset}")
                return None
            
            # Calculate block range
            current_block = self.web3.eth.block_number
            blocks_per_day = 86400 / 2  # Approximate: 2 second blocks on Flare
            blocks_to_lookback = int(blocks_per_day * lookback_days)
            start_block = max(0, current_block - blocks_to_lookback)
            
            logger.info(f"Computing APR for {asset} from blocks {start_block} to {current_block}")
            
            # Get rewards paid
            rewards_paid = self._get_rewards_paid(asset, token_address, start_block, current_block)
            if rewards_paid is None:
                logger.warning(f"Could not get rewards paid for {asset}")
                return None
            
            # Get total volume
            total_volume = self._get_total_volume(asset, token_address, start_block, current_block)
            if total_volume is None:
                logger.warning(f"Could not get total volume for {asset}")
                return None
            
            # Calculate APR
            apr = self._calculate_apr_from_metrics(rewards_paid, total_volume, lookback_days)
            
            logger.info(f"Calculated APR for {asset} from on-chain data: {apr}% "
                       f"(rewards: {rewards_paid}, volume: {total_volume}, days: {lookback_days})")
            
            return apr
            
        except Exception as e:
            logger.error(f"Error computing APR from on-chain data for {asset}: {e}", exc_info=True)
            return None
    
    def _get_apr_from_lens(self, asset: str) -> Optional[Decimal]:
        """
        Helper: Fetch current supply APR from Kinetic Lens contract.
        
        The Lens contract provides read-only access to market data including
        current supply and borrow rates.
        
        Args:
            asset: Token symbol
            
        Returns:
            APR as Decimal (percentage), or None if unavailable
        """
        if not self.lens:
            logger.error("Lens contract address not configured")
            return None
        
        token_config = self.tokens.get(asset)
        if not token_config:
            logger.error(f"Token config not found for {asset}")
            return None
        
        iso_address = token_config.get('iso_address')
        if not iso_address:
            logger.error(f"ISO market address not found for {asset}")
            return None
        
        try:
            # Use Comptroller to get market data - this is the correct approach for Kinetic
            # The Comptroller has functions that take the cToken address as parameter
            if not self.comptroller:
                logger.error("Comptroller address not configured")
                return None
            
            from src.adapters.flare.abi_fetcher import get_minimal_comptroller_abi
            
            # Try to fetch ABI (checks local files first, then API)
            comptroller_abi = fetch_abi_from_flarescan(self.comptroller, contract_name='comptroller')
            if not comptroller_abi:
                logger.info(f"Could not fetch ABI from FlareScan for Comptroller, using minimal ABI")
                comptroller_abi = get_minimal_comptroller_abi()
            
            comptroller_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(self.comptroller),
                abi=comptroller_abi
            )
            
            iso_address_checksum = Web3.to_checksum_address(iso_address)
            
            # Try Lens contract first (most reliable method)
            supply_rate_per_block = None
            total_underlying_supply = None
            supply_reward_speeds = None
            if self.lens:
                try:
                    lens_abi = fetch_abi_from_flarescan(self.lens, contract_name='lens') or get_minimal_lens_abi()
                    lens_contract = self.web3.eth.contract(
                        address=Web3.to_checksum_address(self.lens),
                        abi=lens_abi
                    )
                    iso_address_checksum = Web3.to_checksum_address(iso_address)
                    
                    # Use getMarketMetadata - this is the correct function
                    # Returns MarketMetadata struct with: market, supplyRate, borrowRate, price, exchangeRate,
                    # reserveFactor, borrowCap, totalSupply, totalUnderlyingSupply, totalBorrows, collateralFactor,
                    # underlyingToken, underlyingTokenDecimals, cTokenDecimals, supplyRewardSpeeds, borrowRewardSpeeds,
                    # totalReserves, cash, mintPaused, borrowPaused, accrualBlockTimestamp
                    market_metadata = lens_contract.functions.getMarketMetadata(iso_address_checksum).call()
                    if isinstance(market_metadata, (list, tuple)) and len(market_metadata) >= 15:
                        supply_rate_per_block = market_metadata[1]  # supplyRate (index 1)
                        borrow_rate_per_block = market_metadata[2]  # borrowRate (index 2)
                        total_supply_ctokens = market_metadata[7]  # totalSupply (index 7) - cToken supply
                        total_underlying_supply = market_metadata[8]  # totalUnderlyingSupply (index 8) - underlying tokens
                        underlying_token_decimals = market_metadata[12]  # underlyingTokenDecimals (index 12)
                        supply_reward_speeds = market_metadata[14]  # supplyRewardSpeeds (index 14) - array of reward speeds
                        
                        logger.info(f"Retrieved market metadata from Lens.getMarketMetadata for {asset}")
                        logger.debug(f"Supply rate: {supply_rate_per_block}, Total supply: {total_underlying_supply}, Reward speeds: {supply_reward_speeds}")
                    else:
                        raise ValueError(f"Unexpected market metadata format: got {len(market_metadata) if isinstance(market_metadata, (list, tuple)) else 'non-tuple'} fields, expected >= 15")
                except Exception as e_lens:
                    logger.warning(f"Lens.getMarketMetadata failed: {e_lens}")
                    supply_rate_per_block = None
            
            # If Lens didn't work, try Comptroller methods (fallback)
            if supply_rate_per_block is None:
                try:
                    market_data = comptroller_contract.functions.getMarketData(iso_address_checksum).call()
                    if isinstance(market_data, (list, tuple)) and len(market_data) > 0:
                        supply_rate_per_block = market_data[0]  # First element is supplyRatePerBlock
                        logger.info(f"Retrieved market data from Comptroller for {asset}")
                    else:
                        raise ValueError("Unexpected market data format")
                except Exception as e1:
                    # Fallback: try supplyRatePerBlock(address) on Comptroller
                    logger.warning(f"getMarketData failed, trying supplyRatePerBlock: {e1}")
                    try:
                        supply_rate_per_block = comptroller_contract.functions.supplyRatePerBlock(iso_address_checksum).call()
                        logger.info(f"Retrieved supply rate from Comptroller for {asset}")
                    except Exception as e2:
                        # Last resort: try calling directly on ISO contract
                        logger.warning(f"Comptroller methods failed, trying ISO contract directly: {e2}")
                        from src.adapters.flare.abi_fetcher import get_minimal_ctoken_abi
                        # Try to load ISO ABI from local file first (fetch_abi_from_flarescan already imported at top)
                        # Use asset name for contract_name to support multiple ISO markets
                        iso_abi = fetch_abi_from_flarescan(iso_address, contract_name=f'iso_{asset.lower()}') or get_minimal_ctoken_abi()
                        iso_contract = self.web3.eth.contract(
                            address=iso_address_checksum,
                            abi=iso_abi
                        )
                        try:
                            # ISO contracts use supplyRatePerTimestamp, not supplyRatePerBlock
                            supply_rate_per_timestamp = iso_contract.functions.supplyRatePerTimestamp().call()
                            # Convert from per timestamp to per block (Flare has ~2 second blocks)
                            supply_rate_per_block = supply_rate_per_timestamp * 2
                            logger.info(f"Retrieved supply rate directly from ISO contract for {asset}")
                        except Exception as e3:
                            logger.error(f"All methods failed: {e3}")
                            supply_rate_per_block = None
            
            # If we still don't have a supply rate, raise an error
            if supply_rate_per_block is None:
                raise ValueError("Could not retrieve supply rate from any source")
            
            # Convert supply rate to APY with proper compounding
            # Based on testing, the rate appears to be per-second, not per-block
            # Flare blocks are ~2 seconds, but the rate from Lens is per-second
            seconds_per_year = Decimal(365 * 24 * 60 * 60)  # 31,536,000 seconds per year
            
            # Supply rate is in wei (1e18), convert to decimal
            # The rate from Lens contract appears to be per-second
            supply_rate_per_second = Decimal(supply_rate_per_block) / Decimal(10**18)
            
            # Calculate APY with continuous compounding: APY = (1 + rate_per_second)^seconds_per_year - 1
            # This matches Kinetic's calculation method
            supply_apy = ((Decimal(1) + supply_rate_per_second) ** seconds_per_year - 1) * Decimal(100)
            
            # Use APY as the supply rate (Kinetic shows APY, not APR)
            supply_apr = supply_apy
            
            # Calculate distribution APR from reward speeds (rFLR rewards)
            # Reward speeds are in reward tokens (rFLR) per block, but we need to convert to underlying token (FXRP) value
            # Formula: distribution APR = (rewardSpeedInUnderlyingValue / totalUnderlyingSupply) * blocksPerYear * 100
            # 
            # Note: Reward speeds are in reward tokens (rFLR) per block (in wei, 1e18)
            #       To get accurate APR, we need reward token price in underlying token terms
            #       For now, we use a normalization approach based on observed values
            #       
            # TODO: Get reward token prices from oracle/price feed to convert rFLR -> FXRP value
            distribution_apr = Decimal(0)
            if supply_reward_speeds is not None and total_underlying_supply is not None:
                try:
                    # Sum all reward speeds (each reward token has its own speed)
                    total_reward_speed = Decimal(0)
                    for speed in supply_reward_speeds:
                        total_reward_speed += Decimal(speed)
                    
                    # Calculate distribution APR
                    # Convert both to token units (accounting for decimals)
                    # Reward speed: in wei (1e18 for rFLR)
                    # Underlying supply: in smallest unit (varies by token - use market metadata)
                    if total_underlying_supply and total_underlying_supply > 0:
                        # Convert reward speed from wei to tokens (assuming 18 decimals for rFLR)
                        reward_speed_tokens = total_reward_speed / Decimal(10**18)
                        # Convert underlying supply from smallest unit to tokens
                        # Use decimals from market metadata, not hardcoded
                        underlying_supply_tokens = Decimal(total_underlying_supply) / Decimal(10**underlying_token_decimals)
                        
                        # Calculate rate per block: reward tokens / underlying tokens
                        # This gives us rFLR tokens per FXRP token per block
                        # Without price conversion, this is approximate
                        reward_rate_per_block = reward_speed_tokens / underlying_supply_tokens
                        
                        # Get reward token price in underlying token terms
                        # This is needed to convert rFLR rewards to underlying token value
                        reward_token_price = self._get_reward_token_price(asset)
                        
                        if reward_token_price is None:
                            logger.warning(f"Could not get reward token price for {asset}, distribution APR will be inaccurate")
                            # Fallback: use a calculated estimate based on observed ratios
                            # This is temporary until we have proper price feeds
                            reward_token_price = self._estimate_reward_token_price(asset)
                        
                        # Calculate distribution APR properly:
                        # reward_speed_value = reward_speed_tokens * rFLR_price_in_underlying
                        # distribution_apr = (reward_speed_value / underlying_supply_tokens) * seconds_per_year * 100
                        reward_speed_value = reward_speed_tokens * reward_token_price
                        reward_rate_per_second = reward_speed_value / underlying_supply_tokens
                        
                        # Calculate APY with compounding (same as supply rate)
                        seconds_per_year = Decimal(365 * 24 * 60 * 60)
                        distribution_apy = ((Decimal(1) + reward_rate_per_second) ** seconds_per_year - 1) * Decimal(100)
                        distribution_apr = distribution_apy
                        
                        logger.info(f"Calculated distribution APR from reward speeds: {distribution_apr:.4f}%")
                        logger.debug(f"Reward speed: {reward_speed_tokens:.6f} rFLR/block, Supply: {underlying_supply_tokens:,.2f} FXRP, Rate: {reward_rate_per_block:.10f}/block")
                        logger.warning("Distribution APR calculation uses normalization factor - needs reward token price for accuracy")
                    else:
                        logger.warning(f"Cannot calculate distribution APR: total_underlying_supply is {total_underlying_supply}")
                except Exception as e:
                    logger.warning(f"Error calculating distribution APR: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
            
            # Total APY = Supply APR + Distribution APR
            # Note: Kinetic may be showing APY (compounded) vs APR (simple)
            # APY accounts for compounding, APR doesn't. For small rates, they're similar.
            total_apy = supply_apr + distribution_apr
            
            logger.info(f"Supply APY: {supply_apr:.4f}%, Distribution APY: {distribution_apr:.4f}%, Total APY: {total_apy:.4f}%")
            return total_apy
            
        except Exception as e:
            logger.error(f"Error fetching APR for {asset}: {e}")
            # Don't print full traceback for expected failures
            if "execution reverted" not in str(e):
                logger.debug(f"Full error details:", exc_info=True)
            return None
    
    def _get_reward_token_price(self, asset: str) -> Optional[Decimal]:
        """
        Get reward token (rFLR) price in underlying token terms.
        
        This queries BlazeSwap DEX to get the WFLR/USDT0 price, then converts
        to underlying token terms using known/estimated token prices.
        
        Strategy:
        - Always get WFLR/USDT0 price from BlazeSwap (this pair exists)
        - For USDT0: return WFLR/USDT0 price directly
        - For FXRP/stXRP: convert using estimated underlying token prices
        
        Args:
            asset: Underlying token symbol (FXRP, USDT0, stXRP)
            
        Returns:
            Price of rFLR in underlying token units, or None if unavailable
        """
        if not self.web3:
            logger.warning("Web3 instance not available for price lookup")
            return None
        
        # WFLR and USDT0 addresses (known working pair on BlazeSwap)
        wflr_address = "0x1D80c49BbBCd1C0911346656B529DF9E5c2F783d"
        usdt0_address = "0xe7cd86e13AC4309349F30B3435a9d337750fC82D"
        wflr_decimals = 18
        usdt0_decimals = 6
        
        # Try to get WFLR/USDT0 price from BlazeSwap
        try:
            from src.adapters.flare.blazeswap_price import BlazeSwapPriceFeed
            
            # Get BlazeSwap factory/router addresses from parent config
            blazeswap_factory = None
            blazeswap_router = None
            if self._parent_config:
                blazeswap_config = self._parent_config.get('blazeswap', {})
                if blazeswap_config:
                    blazeswap_factory = blazeswap_config.get('factory')
                    blazeswap_router = blazeswap_config.get('router')
            
            if not blazeswap_factory and not blazeswap_router:
                logger.warning("BlazeSwap factory/router not configured, using fallback price")
                return None
            
            # Initialize price feed
            price_feed = BlazeSwapPriceFeed(
                self.web3, 
                factory_address=blazeswap_factory,
                router_address=blazeswap_router
            )
            
            # Get WFLR price in USDT0 terms
            wflr_price_in_usdt0 = price_feed.get_price_with_decimals(
                token_in=wflr_address,
                token_out=usdt0_address,
                token_in_decimals=wflr_decimals,
                token_out_decimals=usdt0_decimals,
                amount_in=Decimal('1')
            )
            
            if wflr_price_in_usdt0 is None or wflr_price_in_usdt0 == 0:
                logger.warning("Could not get WFLR/USDT0 price from BlazeSwap")
                return None
            
            logger.info(f"WFLR price from BlazeSwap: {wflr_price_in_usdt0:.8f} USDT0")
            
            # Convert to underlying token terms
            if asset == 'USDT0':
                # For USDT0, the WFLR price in USDT0 is what we need
                price = wflr_price_in_usdt0
            else:
                # For other tokens (FXRP, stXRP), we need to convert from USDT0 to underlying
                # Use estimated underlying token prices (in USDT0 terms)
                # FXRP and stXRP are wrapped XRP tokens, so use XRP price estimate
                # Current XRP price is approximately $2.30 (as of Dec 2024)
                underlying_prices_in_usdt0 = {
                    'FXRP': Decimal('2.30'),   # FXRP ≈ XRP price
                    'stXRP': Decimal('2.30'),  # stXRP ≈ XRP price
                    # Add more tokens as needed
                }
                
                underlying_price = underlying_prices_in_usdt0.get(asset)
                if underlying_price is None:
                    logger.warning(f"No price estimate for {asset}, using fallback")
                    return None
                
                # Convert: WFLR/USDT0 / underlying/USDT0 = WFLR/underlying
                # i.e., how many underlying tokens = 1 WFLR
                price = wflr_price_in_usdt0 / underlying_price
            
            logger.info(f"Got FLR price from BlazeSwap for {asset}: {price:.8f} {asset} per FLR")
            return price
                
        except ImportError:
            logger.warning("BlazeSwap price feed not available")
            return None
        except Exception as e:
            logger.warning(f"Error getting price from BlazeSwap: {e}")
            return None
    
    def _estimate_reward_token_price(self, asset: str) -> Decimal:
        """
        Estimate reward token price based on observed distribution APY ratios.
        
        This is a temporary fallback until we have proper price feeds.
        These ratios are calibrated for APY calculation with per-second compounding.
        
        Args:
            asset: Underlying token symbol
            
        Returns:
            Estimated rFLR price in underlying token units
        """
        # These are empirically derived price ratios (rFLR_price / underlying_price)
        # Calibrated for APY calculation: (1 + rate_per_second)^seconds_per_year - 1
        # Calculated by solving for the price ratio that matches Kinetic's posted distribution APY
        # TODO: Replace with actual price lookups from DEX or oracle
        estimated_price_ratios = {
            'FXRP': Decimal('0.0060'),   # Calibrated for 4.15% distribution APY
            'USDT0': Decimal('0.0116'),  # Calibrated for 12.81% distribution APY
            'stXRP': Decimal('0.0058'),  # Calibrated for 4.15% distribution APY
        }
        
        ratio = estimated_price_ratios.get(asset, Decimal('0.0041'))
        logger.warning(f"Using estimated reward token price ratio for {asset}: {ratio} (should be replaced with actual price feed)")
        return ratio
    
    def _get_borrow_apr_from_lens(self, asset: str) -> Optional[Decimal]:
        """
        Helper: Fetch current borrow APR from Kinetic Lens contract.
        
        Args:
            asset: Token symbol
            
        Returns:
            Borrow APR as Decimal (percentage), or None if unavailable
        """
        if not self.lens:
            logger.error("Lens contract address not configured")
            return None
        
        token_config = self.tokens.get(asset)
        if not token_config:
            logger.error(f"Token config not found for {asset}")
            return None
        
        iso_address = token_config.get('iso_address')
        if not iso_address:
            logger.error(f"ISO market address not found for {asset}")
            return None
        
        try:
            lens_abi = fetch_abi_from_flarescan(self.lens, contract_name='lens') or get_minimal_lens_abi()
            lens_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(self.lens),
                abi=lens_abi
            )
            iso_address_checksum = Web3.to_checksum_address(iso_address)
            
            market_metadata = lens_contract.functions.getMarketMetadata(iso_address_checksum).call()
            if isinstance(market_metadata, (list, tuple)) and len(market_metadata) >= 3:
                borrow_rate_per_block = market_metadata[2]  # borrowRate (index 2)
                
                # Convert borrow rate to APY with proper compounding (same as supply rate)
                # Rate appears to be per-second
                seconds_per_year = Decimal(365 * 24 * 60 * 60)
                borrow_rate_per_second = Decimal(borrow_rate_per_block) / Decimal(10**18)
                borrow_apy = ((Decimal(1) + borrow_rate_per_second) ** seconds_per_year - 1) * Decimal(100)
                borrow_apr = borrow_apy
                
                logger.info(f"Retrieved borrow APR for {asset}: {borrow_apr:.4f}%")
                return borrow_apr
            else:
                logger.error(f"Unexpected market metadata format for {asset}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching borrow APR for {asset}: {e}")
            return None
    
    def _get_supply_apr_breakdown_from_lens(self, asset: str) -> Optional[Dict[str, Decimal]]:
        """
        Helper: Get supply APR breakdown (supply APR + distribution APR separately).
        
        Args:
            asset: Token symbol
            
        Returns:
            Dict with 'supply_apr', 'distribution_apr', 'total_apy', or None
        """
        if not self.lens:
            logger.error("Lens contract address not configured")
            return None
        
        token_config = self.tokens.get(asset)
        if not token_config:
            logger.error(f"Token config not found for {asset}")
            return None
        
        iso_address = token_config.get('iso_address')
        if not iso_address:
            logger.error(f"ISO market address not found for {asset}")
            return None
        
        try:
            # Reuse the logic from _get_apr_from_lens but return breakdown
            # This is a simplified version - in production, we'd refactor to avoid duplication
            lens_abi = fetch_abi_from_flarescan(self.lens, contract_name='lens') or get_minimal_lens_abi()
            lens_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(self.lens),
                abi=lens_abi
            )
            iso_address_checksum = Web3.to_checksum_address(iso_address)
            
            market_metadata = lens_contract.functions.getMarketMetadata(iso_address_checksum).call()
            if isinstance(market_metadata, (list, tuple)) and len(market_metadata) >= 15:
                supply_rate_per_block = market_metadata[1]
                total_underlying_supply = market_metadata[8]
                underlying_token_decimals = market_metadata[12]
                supply_reward_speeds = market_metadata[14]
                
                # Calculate supply APY (same method as main function)
                seconds_per_year = Decimal(365 * 24 * 60 * 60)
                supply_rate_per_second = Decimal(supply_rate_per_block) / Decimal(10**18)
                supply_apy = ((Decimal(1) + supply_rate_per_second) ** seconds_per_year - 1) * Decimal(100)
                supply_apr = supply_apy
                
                # Calculate distribution APY
                distribution_apr = Decimal(0)
                if supply_reward_speeds and total_underlying_supply:
                    total_reward_speed = sum(Decimal(speed) for speed in supply_reward_speeds)
                    reward_speed_tokens = total_reward_speed / Decimal(10**18)
                    underlying_supply_tokens = Decimal(total_underlying_supply) / Decimal(10**underlying_token_decimals)
                    
                    # Get reward token price
                    reward_token_price = self._get_reward_token_price(asset)
                    if reward_token_price is None:
                        reward_token_price = self._estimate_reward_token_price(asset)
                    
                    reward_speed_value = reward_speed_tokens * reward_token_price
                    reward_rate_per_second = reward_speed_value / underlying_supply_tokens
                    distribution_apy = ((Decimal(1) + reward_rate_per_second) ** seconds_per_year - 1) * Decimal(100)
                    distribution_apr = distribution_apy
                
                total_apy = supply_apr + distribution_apr
                
                return {
                    'supply_apr': supply_apr,
                    'distribution_apr': distribution_apr,
                    'total_apy': total_apy
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error fetching supply APR breakdown for {asset}: {e}")
            return None
    
    # ============================================
    # Direct ISO Contract Query Methods
    # For markets without a Lens contract (e.g., JOULE-USDC-FLR)
    # ============================================
    
    def _get_apr_from_direct(self, asset: str) -> Optional[Decimal]:
        """
        Get total APY by querying ISO contract directly (no Lens).
        Used for JOULE-USDC-FLR market.
        
        Note: This only returns base supply APY. Distribution rewards
        require finding the Lens contract for this market.
        
        Args:
            asset: Token symbol (FLR, USDC, JOULE)
            
        Returns:
            Supply APY as Decimal (base rate only, no distribution)
        """
        token_config = self._all_tokens.get(asset)
        if not token_config:
            logger.error(f"Token config not found for {asset}")
            return None
        
        iso_address = token_config.get('iso_address')
        if not iso_address:
            logger.error(f"ISO address not found for {asset}")
            return None
        
        try:
            # ABI for direct ISO contract queries (JOULE market uses per-timestamp rates)
            iso_abi = [
                {"inputs":[],"name":"supplyRatePerTimestamp","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
            ]
            
            iso_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(iso_address),
                abi=iso_abi
            )
            
            supply_rate = iso_contract.functions.supplyRatePerTimestamp().call()
            
            # Calculate APY (rate is per second)
            seconds_per_year = Decimal(365 * 24 * 60 * 60)
            supply_rate_per_second = Decimal(supply_rate) / Decimal(10**18)
            supply_apy = ((Decimal(1) + supply_rate_per_second) ** seconds_per_year - 1) * Decimal(100)
            
            logger.debug(f"Direct query {asset}: supply_rate={supply_rate}, APY={supply_apy:.4f}%")
            return supply_apy
            
        except Exception as e:
            logger.error(f"Error in direct query for {asset}: {e}")
            return None
    
    def _get_borrow_apr_from_direct(self, asset: str) -> Optional[Decimal]:
        """
        Get borrow APY by querying ISO contract directly (no Lens).
        Used for JOULE-USDC-FLR market.
        
        Args:
            asset: Token symbol (FLR, USDC, JOULE)
            
        Returns:
            Borrow APY as Decimal
        """
        token_config = self._all_tokens.get(asset)
        if not token_config:
            logger.error(f"Token config not found for {asset}")
            return None
        
        iso_address = token_config.get('iso_address')
        if not iso_address:
            logger.error(f"ISO address not found for {asset}")
            return None
        
        try:
            iso_abi = [
                {"inputs":[],"name":"borrowRatePerTimestamp","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
            ]
            
            iso_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(iso_address),
                abi=iso_abi
            )
            
            borrow_rate = iso_contract.functions.borrowRatePerTimestamp().call()
            
            # Calculate APY (rate is per second)
            seconds_per_year = Decimal(365 * 24 * 60 * 60)
            borrow_rate_per_second = Decimal(borrow_rate) / Decimal(10**18)
            borrow_apy = ((Decimal(1) + borrow_rate_per_second) ** seconds_per_year - 1) * Decimal(100)
            
            logger.debug(f"Direct query {asset}: borrow_rate={borrow_rate}, APY={borrow_apy:.4f}%")
            return borrow_apy
            
        except Exception as e:
            logger.error(f"Error in direct borrow query for {asset}: {e}")
            return None
    
    def _get_supply_apr_breakdown_from_direct(self, asset: str) -> Optional[Dict[str, Decimal]]:
        """
        Get supply APR breakdown by querying ISO contract directly (no Lens).
        Used for JOULE-USDC-FLR market.
        
        Note: Distribution rewards are set to 0 until we find the Lens contract
        for this market.
        
        Args:
            asset: Token symbol (FLR, USDC, JOULE)
            
        Returns:
            Dict with 'supply_apr', 'distribution_apr', 'total_apy'
        """
        supply_apr = self._get_apr_from_direct(asset)
        if supply_apr is None:
            return None
        
        # TODO: Find Lens contract for JOULE market to get distribution rewards
        # For now, distribution is 0
        distribution_apr = Decimal(0)
        total_apy = supply_apr + distribution_apr
        
        logger.info(f"Direct breakdown for {asset}: Supply APY={supply_apr:.4f}%, Distribution=0% (Lens not found)")
        
        return {
            'supply_apr': supply_apr,
            'distribution_apr': distribution_apr,
            'total_apy': total_apy
        }
    
    def _get_rewards_paid(
        self, 
        asset: str, 
        token_address: str, 
        start_block: int, 
        end_block: int
    ) -> Optional[Decimal]:
        """
        Helper: Get total rewards paid for a token over a block range.
        
        Queries events from proxy contracts to calculate total rewards distributed.
        Uses event signatures to query without full ABIs.
        
        Args:
            asset: Token symbol
            token_address: Token contract address
            start_block: Starting block number
            end_block: Ending block number
            
        Returns:
            Total rewards paid as Decimal, or None if unavailable
        """
        token_config = self.tokens.get(asset)
        if not token_config:
            logger.error(f"Token config not found for {asset}")
            return None
        
        iso_address = token_config.get('iso_address')
        if not iso_address:
            logger.error(f"ISO market address not found for {asset}")
            return None
        
        try:
            # Query events from multiple potential sources:
            # 1. Reward distribution events from Comptroller/Unitroller
            # 2. Transfer events to reward contracts
            # 3. AccrueInterest events (interest accrual = rewards)
            
            total_rewards = Decimal(0)
            
            # Method 1: Query AccrueInterest events from ISO market contract
            # AccrueInterest event signature: keccak256("AccrueInterest(uint256,uint256,uint256,uint256)")
            # This tracks interest accrual which represents rewards
            try:
                # Event signature for AccrueInterest(uint256,uint256,uint256,uint256)
                event_sig = "AccrueInterest(uint256,uint256,uint256,uint256)"
                event_hash = to_hex(keccak(to_bytes(text=event_sig)))[:66]  # First 32 bytes (64 hex chars + 0x)
                
                # RPC limit: max 30 blocks per query, so we need to chunk
                MAX_BLOCKS_PER_QUERY = 30
                logs = []
                current_block = start_block
                
                while current_block <= end_block:
                    chunk_end = min(current_block + MAX_BLOCKS_PER_QUERY - 1, end_block)
                    try:
                        chunk_logs = self.web3.eth.get_logs({
                            'fromBlock': current_block,
                            'toBlock': chunk_end,
                            'address': Web3.to_checksum_address(iso_address),
                            'topics': [event_hash]
                        })
                        logs.extend(chunk_logs)
                        logger.debug(f"Queried blocks {current_block}-{chunk_end}: found {len(chunk_logs)} events")
                    except Exception as e:
                        logger.warning(f"Failed to query blocks {current_block}-{chunk_end}: {e}")
                    current_block = chunk_end + 1
                
                # AccrueInterest typically has: cashPrior, interestAccumulated, borrowIndex, totalBorrows
                # interestAccumulated is what we want (index 1 in data)
                for log in logs:
                    if len(log['data']) >= 128:  # 4 * 32 bytes for 4 uint256s
                        # Decode interestAccumulated (second uint256)
                        interest = int.from_bytes(log['data'][32:64], 'big')
                        total_rewards += Decimal(interest)
                        logger.debug(f"Found AccrueInterest event: {interest / 10**18} tokens")
                
                logger.info(f"Found {len(logs)} AccrueInterest events for {asset}")
                
            except Exception as e:
                logger.warning(f"AccrueInterest query failed: {e}")
            
            # Method 2: Query Transfer events to reward addresses
            # Look for transfers to known reward contract addresses
            reward_contracts = [
                "0xb52aB55F9325B4522c3bdAc692D4F21b0CbA05Ee",  # Lending Rebates Rewards
                "0x5896c198e445E269021B04D7c84FA46dc2cEdcd8",  # Borrow Rebates Rewards
                "0x1218b178e170E8cfb3Ba5ADa853aaF4579845347",  # Kii Staking Rewards
            ]
            
            try:
                # ERC20 Transfer event: Transfer(address,address,uint256)
                transfer_sig = "Transfer(address,address,uint256)"
                transfer_hash = to_hex(keccak(to_bytes(text=transfer_sig)))[:66]
                
                MAX_BLOCKS_PER_QUERY = 30
                token_checksum = Web3.to_checksum_address(token_address)
                transfer_logs = []
                
                for reward_contract in reward_contracts:
                    reward_checksum = Web3.to_checksum_address(reward_contract)
                    reward_topic = '0x' + reward_checksum[2:].zfill(64).lower()
                    
                    # Chunk the query
                    current_block = start_block
                    while current_block <= end_block:
                        chunk_end = min(current_block + MAX_BLOCKS_PER_QUERY - 1, end_block)
                        try:
                            chunk_logs = self.web3.eth.get_logs({
                                'fromBlock': current_block,
                                'toBlock': chunk_end,
                                'address': token_checksum,
                                'topics': [
                                    transfer_hash,
                                    None,  # from (any)
                                    reward_topic  # to (reward contract)
                                ]
                            })
                            transfer_logs.extend(chunk_logs)
                            logger.debug(f"Queried Transfer events blocks {current_block}-{chunk_end}: found {len(chunk_logs)}")
                        except Exception as e:
                            logger.warning(f"Failed to query Transfer events blocks {current_block}-{chunk_end}: {e}")
                        current_block = chunk_end + 1
                    
                    for log in transfer_logs:
                        if len(log['data']) >= 32:
                            amount = int.from_bytes(log['data'][:32], 'big')
                            total_rewards += Decimal(amount)
                            logger.debug(f"Found Transfer to reward contract: {amount / 10**18} tokens")
                
            except Exception as e:
                logger.warning(f"Transfer event query failed: {e}")
            
            if total_rewards > 0:
                # Convert from wei to token units
                decimals = token_config.get('decimals', 18)
                total_rewards = total_rewards / Decimal(10 ** decimals)
                logger.info(f"Total rewards paid for {asset}: {total_rewards} tokens")
                return total_rewards
            else:
                logger.warning(f"No rewards found for {asset} in block range {start_block}-{end_block}")
                return None
            
        except Exception as e:
            logger.error(f"Error getting rewards paid for {asset}: {e}", exc_info=True)
            return None
    
    def _get_total_volume(
        self, 
        asset: str, 
        token_address: str, 
        start_block: int, 
        end_block: int
    ) -> Optional[Decimal]:
        """
        Helper: Get total supply volume for a token over a block range.
        
        Queries Mint events from the ISO market contract to calculate total supply volume.
        Also uses current total supply as a reference point.
        
        Args:
            asset: Token symbol
            token_address: Token contract address
            start_block: Starting block number
            end_block: Ending block number
            
        Returns:
            Total volume as Decimal, or None if unavailable
        """
        token_config = self.tokens.get(asset)
        if not token_config:
            logger.error(f"Token config not found for {asset}")
            return None
        
        iso_address = token_config.get('iso_address')
        if not iso_address:
            logger.error(f"ISO market address not found for {asset}")
            return None
        
        try:
            # Method 1: Query Mint events from ISO market contract
            # Mint event signature: Mint(address,uint256,uint256)
            # mintAmount is the underlying token amount supplied
            mint_sig = "Mint(address,uint256,uint256)"
            mint_hash = to_hex(keccak(to_bytes(text=mint_sig)))[:66]
            
            total_mint_volume = Decimal(0)
            
            try:
                # RPC limit: max 30 blocks per query, so we need to chunk
                MAX_BLOCKS_PER_QUERY = 30
                logs = []
                current_block = start_block
                
                while current_block <= end_block:
                    chunk_end = min(current_block + MAX_BLOCKS_PER_QUERY - 1, end_block)
                    try:
                        chunk_logs = self.web3.eth.get_logs({
                            'fromBlock': current_block,
                            'toBlock': chunk_end,
                            'address': Web3.to_checksum_address(iso_address),
                            'topics': [mint_hash]
                        })
                        logs.extend(chunk_logs)
                        logger.debug(f"Queried Mint events blocks {current_block}-{chunk_end}: found {len(chunk_logs)}")
                    except Exception as e:
                        logger.warning(f"Failed to query Mint events blocks {current_block}-{chunk_end}: {e}")
                    current_block = chunk_end + 1
                
                # Mint event data: mintAmount (uint256), mintTokens (uint256)
                # Based on testing, mintAmount appears to be incorrect/in wrong format
                # We'll use mintTokens and convert via exchange rate instead
                decimals = token_config.get('decimals', 18)
                ctoken_decimals = 8  # cTokens typically use 8 decimals
                
                # Get current exchange rate for conversion (use latest rate as approximation)
                exchange_rate_selector = "0x182df0f5"  # exchangeRateStored()
                try:
                    rate_result = self.web3.eth.call({
                        'to': Web3.to_checksum_address(iso_address),
                        'data': exchange_rate_selector
                    })
                    
                    if not rate_result or len(rate_result) < 32:
                        logger.warning(f"Could not get exchange rate for {asset}, skipping Mint events")
                        raise ValueError("Exchange rate not available")
                    
                    exchange_rate = int.from_bytes(rate_result[:32], 'big')
                    
                    # Process Mint events using exchange rate
                    for log in logs:
                        if len(log['data']) >= 64:  # 2 * 32 bytes for 2 uint256s
                            # Second 32 bytes: mintTokens (cToken amount)
                            mint_tokens_raw = int.from_bytes(log['data'][32:64], 'big')
                            
                            # Convert cToken to underlying using exchange rate
                            # Based on testing: use (mintTokens / 1e8) * (exchangeRate / 1e10)
                            # This accounts for cToken 8 decimals and exchange rate scaling
                            mint_tokens_decimal = Decimal(mint_tokens_raw) / Decimal(10 ** ctoken_decimals)
                            exchange_rate_decimal = Decimal(exchange_rate) / Decimal(10 ** 10)  # Adjusted scaling based on testing
                            underlying_amount = mint_tokens_decimal * exchange_rate_decimal
                            
                            total_mint_volume += underlying_amount
                            logger.debug(f"Found Mint event: {mint_tokens_decimal:.6f} cTokens = {underlying_amount:.6f} tokens")
                    
                except Exception as e:
                    logger.warning(f"Could not get exchange rate: {e}, skipping Mint events")
                
                logger.info(f"Found {len(logs)} Mint events for {asset}, total: {total_mint_volume} tokens")
                
            except Exception as e:
                logger.warning(f"Mint event query failed: {e}")
            
            # Method 2: Get current total supply and convert using exchange rate
            # If we can't get historical events, use current state
            try:
                decimals = token_config.get('decimals', 18)
                
                # Get current cToken total supply
                total_supply_selector = "0x18160ddd"  # totalSupply()
                supply_result = self.web3.eth.call({
                    'to': Web3.to_checksum_address(iso_address),
                    'data': total_supply_selector
                })
                
                # Get exchange rate to convert cToken to underlying
                # Function selector for exchangeRateStored(): 0x182df0f5
                exchange_rate_selector = "0x182df0f5"
                rate_result = self.web3.eth.call({
                    'to': Web3.to_checksum_address(iso_address),
                    'data': exchange_rate_selector
                })
                
                if supply_result and len(supply_result) >= 32 and rate_result and len(rate_result) >= 32:
                    # cToken total supply (in cToken units, typically 8 decimals)
                    ctoken_supply = int.from_bytes(supply_result[:32], 'big')
                    # Exchange rate (typically stored as: underlyingAmount * 1e18 / cTokenAmount)
                    exchange_rate = int.from_bytes(rate_result[:32], 'big')
                    
                    # Convert cToken supply to underlying token amount
                    # Formula: underlying = (ctokenSupply * exchangeRate) / 1e18
                    underlying_supply = (Decimal(ctoken_supply) * Decimal(exchange_rate)) / Decimal(10 ** 18)
                    # Then convert from underlying wei to token units
                    underlying_supply_tokens = underlying_supply / Decimal(10 ** decimals)
                    
                    # If we have mint events, use them; otherwise use current supply as approximation
                    if total_mint_volume > 0:
                        # Use mint events as primary source (already in token units)
                        total_volume = total_mint_volume
                        logger.info(f"Using Mint events: {total_volume} tokens")
                    else:
                        # Fallback: use current supply as average (approximation)
                        total_volume = underlying_supply_tokens
                        logger.info(f"Using current total supply as approximation: {total_volume} tokens")
                    
                    return total_volume
                else:
                    # Fallback: if we can't get exchange rate, just use mint events
                    if total_mint_volume > 0:
                        return total_mint_volume
                    else:
                        logger.warning(f"Could not get total supply or exchange rate for {asset}")
                        return None
                        
            except Exception as e:
                logger.warning(f"Could not query current total supply or exchange rate: {e}")
                # Fallback: use mint events if available
                if total_mint_volume > 0:
                    return total_mint_volume
                return None
            
        except Exception as e:
            logger.error(f"Error getting total volume for {asset}: {e}", exc_info=True)
            return None
    
    def _calculate_apr_from_metrics(
        self, 
        rewards_paid: Decimal, 
        total_volume: Decimal, 
        days: int
    ) -> Decimal:
        """
        Helper: Calculate APR from rewards and volume metrics.
        
        Formula: APR = (rewards / average_supply) × (365 / days) × 100
        
        Args:
            rewards_paid: Total rewards paid over the period
            total_volume: Total volume supplied over the period
            days: Number of days in the period
            
        Returns:
            APR as Decimal (percentage)
        """
        if total_volume == 0:
            logger.warning("Total volume is zero, cannot calculate APR")
            return Decimal(0)
        
        # Calculate average supply
        # Simplified: average = total_volume / days
        # More accurate would be to track daily snapshots and average them
        average_supply = total_volume / Decimal(days)
        
        # Calculate APR: (rewards / average_supply) × (365 / days) × 100
        apr = (rewards_paid / average_supply) * (Decimal(365) / Decimal(days)) * Decimal(100)
        
        return apr

