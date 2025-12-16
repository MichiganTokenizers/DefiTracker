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
    
    # FXRP-USDT0-stXRP pool tokens
    POOL_TOKENS = ['FXRP', 'USDT0', 'stXRP']
    
    def __init__(self, protocol_name: str, config: Dict):
        super().__init__(protocol_name, config)
        self.tokens = config.get('tokens', {})
        self.unitroller = config.get('unitroller')
        self.comptroller = config.get('comptroller')
        self.lens = config.get('lens')  # Lens contract for reading market data
        self.web3 = None  # Will be set by chain adapter
        
    def set_web3_instance(self, web3: Web3):
        """Set Web3 instance from chain adapter"""
        self.web3 = web3
    
    def get_supported_assets(self) -> List[str]:
        """
        Get list of assets in the FXRP-USDT0-stXRP pool.
        
        Returns:
            List of asset symbols: ['FXRP', 'USDT0', 'stXRP']
        """
        return self.POOL_TOKENS.copy()
    
    def get_supply_apr(self, asset: str) -> Optional[Decimal]:
        """
        Method 1: Get supply APR directly from Kinetic Lens contract (on-chain).
        
        Kinetic doesn't provide REST API, so we query the Lens contract
        which provides read-only market data.
        
        Args:
            asset: Token symbol (FXRP, USDT0, or stXRP)
            
        Returns:
            APR as Decimal (e.g., 3.83 for 3.83%), or None if unavailable
        """
        if asset not in self.POOL_TOKENS:
            logger.warning(f"Asset {asset} not in FXRP-USDT0-stXRP pool")
            return None
        
        if not self.web3:
            logger.error("Web3 instance not set. Cannot query Lens contract.")
            return None
        
        try:
            apr = self._get_apr_from_lens(asset)
            if apr is not None:
                logger.info(f"Retrieved APR for {asset} from Lens contract: {apr}%")
            return apr
        except Exception as e:
            logger.error(f"Error fetching APR from Lens for {asset}: {e}")
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
            asset: Token symbol (FXRP, USDT0, or stXRP)
            lookback_days: Number of days to look back (default 7)
            
        Returns:
            APR as Decimal, or None if computation fails
        """
        if asset not in self.POOL_TOKENS:
            logger.warning(f"Asset {asset} not in FXRP-USDT0-stXRP pool")
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
            if self.lens:
                try:
                    lens_abi = fetch_abi_from_flarescan(self.lens, contract_name='lens') or get_minimal_lens_abi()
                    lens_contract = self.web3.eth.contract(
                        address=Web3.to_checksum_address(self.lens),
                        abi=lens_abi
                    )
                    iso_address_checksum = Web3.to_checksum_address(iso_address)
                    
                    # Use getMarketMetadata - this is the correct function
                    market_metadata = lens_contract.functions.getMarketMetadata(iso_address_checksum).call()
                    if isinstance(market_metadata, (list, tuple)) and len(market_metadata) >= 2:
                        supply_rate_per_block = market_metadata[1]  # supplyRate is second field
                        logger.info(f"Retrieved supply rate from Lens.getMarketMetadata for {asset}")
                    else:
                        raise ValueError("Unexpected market metadata format")
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
                        iso_abi = get_minimal_ctoken_abi()
                        iso_contract = self.web3.eth.contract(
                            address=iso_address_checksum,
                            abi=iso_abi
                        )
                        try:
                            supply_rate_per_block = iso_contract.functions.supplyRatePerBlock().call()
                            logger.info(f"Retrieved supply rate directly from ISO contract for {asset}")
                        except Exception as e3:
                            logger.error(f"All methods failed: {e3}")
                            supply_rate_per_block = None
            
            # If we still don't have a supply rate, raise an error
            if supply_rate_per_block is None:
                raise ValueError("Could not retrieve supply rate from any source")
            
            # Convert supply rate per block to APR
            # Flare has ~2 second blocks, so blocks per year = 365 * 24 * 60 * 60 / 2
            blocks_per_year = Decimal(365 * 24 * 60 * 60 / 2)  # ~15,768,000 blocks per year
            
            # Supply rate is typically in wei (1e18), so we need to convert
            # APR = (supplyRatePerBlock / 1e18) * blocksPerYear * 100
            supply_rate_decimal = Decimal(supply_rate_per_block) / Decimal(10**18)
            apr = supply_rate_decimal * blocks_per_year * Decimal(100)
            
            logger.info(f"Retrieved supply rate for {asset}: {supply_rate_per_block} per block = {apr}% APR")
            return apr
            
        except Exception as e:
            logger.error(f"Error fetching APR for {asset}: {e}")
            # Don't print full traceback for expected failures
            if "execution reverted" not in str(e):
                logger.debug(f"Full error details:", exc_info=True)
            return None
    
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

