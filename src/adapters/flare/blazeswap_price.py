"""BlazeSwap DEX price feed for Flare blockchain"""
from typing import Optional
from decimal import Decimal
import logging
from web3 import Web3
from src.adapters.flare.abi_fetcher import fetch_abi_from_flarescan

logger = logging.getLogger(__name__)

# Uniswap V2 Router ABI (minimal - just what we need for price queries)
UNISWAP_V2_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "WETH",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Uniswap V2 Factory ABI (minimal - for finding pair addresses)
UNISWAP_V2_FACTORY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"}
        ],
        "name": "getPair",
        "outputs": [{"internalType": "address", "name": "pair", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Uniswap V2 Pair ABI (minimal - for direct reserve queries)
# Compatible with BlazeSwapBasePair
UNISWAP_V2_PAIR_ABI = [
    {
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"internalType": "uint112", "name": "_reserve0", "type": "uint112"},
            {"internalType": "uint112", "name": "_reserve1", "type": "uint112"},
            {"internalType": "uint32", "name": "_blockTimestampLast", "type": "uint32"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]


class BlazeSwapPriceFeed:
    """Price feed using BlazeSwap DEX"""
    
    def __init__(self, web3: Web3, factory_address: Optional[str] = None, router_address: Optional[str] = None):
        """
        Initialize BlazeSwap price feed.
        
        Can use either factory (to find pairs) or router (for getAmountsOut).
        Factory approach is recommended as it's more reliable.
        
        Args:
            web3: Web3 instance for Flare network
            factory_address: BlazeSwap factory contract address (recommended)
            router_address: BlazeSwap router contract address (optional)
        """
        self.web3 = web3
        self.factory_address = factory_address
        self.router_address = router_address
        self.factory_contract = None
        self.router_contract = None
        
        if factory_address:
            self._initialize_factory()
        if router_address:
            self._initialize_router()
    
    def _initialize_factory(self):
        """Initialize factory contract"""
        try:
            # Verify contract exists
            code = self.web3.eth.get_code(Web3.to_checksum_address(self.factory_address))
            if not code or len(code) <= 2:
                logger.warning(f"No contract found at factory address: {self.factory_address}")
                self.factory_contract = None
                return
            
            # Try to fetch ABI from FlareScan first
            factory_abi = fetch_abi_from_flarescan(self.factory_address, contract_name='blazeswap_factory')
            if not factory_abi:
                # Fallback to minimal Uniswap V2 factory ABI
                factory_abi = UNISWAP_V2_FACTORY_ABI
                logger.info("Using minimal Uniswap V2 factory ABI for BlazeSwap")
            
            self.factory_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(self.factory_address),
                abi=factory_abi
            )
            logger.info(f"BlazeSwap factory initialized at {self.factory_address}")
        except Exception as e:
            logger.warning(f"Failed to initialize BlazeSwap factory: {e}")
            self.factory_contract = None
    
    def _initialize_router(self):
        """Initialize router contract"""
        try:
            # Verify contract exists
            code = self.web3.eth.get_code(Web3.to_checksum_address(self.router_address))
            if not code or len(code) <= 2:
                logger.warning(f"No contract found at router address: {self.router_address}")
                self.router_contract = None
                return
            
            # Try to fetch ABI from FlareScan first
            router_abi = fetch_abi_from_flarescan(self.router_address, contract_name='blazeswap_router')
            if not router_abi:
                # Fallback to minimal Uniswap V2 ABI
                router_abi = UNISWAP_V2_ROUTER_ABI
                logger.info("Using minimal Uniswap V2 router ABI for BlazeSwap")
            
            self.router_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(self.router_address),
                abi=router_abi
            )
            logger.info(f"BlazeSwap router initialized at {self.router_address}")
        except Exception as e:
            logger.warning(f"Failed to initialize BlazeSwap router: {e}")
            self.router_contract = None
    
    def get_price(
        self, 
        token_in: str, 
        token_out: str, 
        amount_in: Decimal = Decimal('1')
    ) -> Optional[Decimal]:
        """
        Get price of token_in in terms of token_out using BlazeSwap.
        
        Args:
            token_in: Address of input token (e.g., rFLR)
            token_out: Address of output token (e.g., USDT0, FXRP)
            amount_in: Amount of token_in (default: 1 token)
            
        Returns:
            Price as Decimal (amount_out / amount_in), or None if unavailable
        """
        if not self.router_contract:
            logger.error("Router contract not initialized")
            return None
        
        try:
            # Convert amount_in to wei (assuming 18 decimals for input token)
            # For more accuracy, we'd need to know token decimals
            amount_in_wei = int(amount_in * Decimal(10**18))
            
            # Build path: [token_in, token_out]
            path = [
                Web3.to_checksum_address(token_in),
                Web3.to_checksum_address(token_out)
            ]
            
            # Query router for output amount
            amounts = self.router_contract.functions.getAmountsOut(
                amount_in_wei,
                path
            ).call()
            
            if len(amounts) >= 2:
                amount_out_wei = amounts[1]
                # Convert to decimal (assuming 18 decimals for output token)
                # TODO: Get actual token decimals
                amount_out = Decimal(amount_out_wei) / Decimal(10**18)
                
                # Price = amount_out / amount_in
                price = amount_out / amount_in
                
                logger.debug(f"BlazeSwap price: {amount_in} {token_in} = {amount_out} {token_out} (price: {price})")
                return price
            else:
                logger.warning(f"Unexpected amounts array length: {len(amounts)}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting price from BlazeSwap: {e}")
            return None
    
    def get_price_with_decimals(
        self,
        token_in: str,
        token_out: str,
        token_in_decimals: int,
        token_out_decimals: int,
        amount_in: Decimal = Decimal('1')
    ) -> Optional[Decimal]:
        """
        Get price with explicit decimal handling.
        
        Tries factory/pair approach first, falls back to router if available.
        
        Args:
            token_in: Address of input token
            token_out: Address of output token
            token_in_decimals: Decimals of input token
            token_out_decimals: Decimals of output token
            amount_in: Amount of token_in (default: 1 token)
            
        Returns:
            Price as Decimal (amount_out / amount_in), or None if unavailable
        """
        # Try factory/pair approach first (more reliable)
        if self.factory_contract:
            price = self._get_price_from_pair(token_in, token_out, token_in_decimals, token_out_decimals)
            if price is not None:
                return price
            # If factory is available but pair doesn't exist, that's fine - just return None
            # Don't fall through to router if pair doesn't exist
        
        # Fallback to router if available
        if self.router_contract:
            try:
                # Convert amount_in to token's smallest unit
                amount_in_wei = int(amount_in * Decimal(10**token_in_decimals))
                
                # Build path
                path = [
                    Web3.to_checksum_address(token_in),
                    Web3.to_checksum_address(token_out)
                ]
                
                # Query router
                amounts = self.router_contract.functions.getAmountsOut(
                    amount_in_wei,
                    path
                ).call()
                
                if len(amounts) >= 2:
                    amount_out_wei = amounts[1]
                    # Convert to decimal using actual token decimals
                    amount_out = Decimal(amount_out_wei) / Decimal(10**token_out_decimals)
                    
                    # Price = amount_out / amount_in
                    price = amount_out / amount_in
                    
                    logger.debug(f"BlazeSwap price (router): {amount_in} {token_in} = {amount_out} {token_out} (price: {price})")
                    return price
            except Exception as e:
                logger.debug(f"Router query failed: {e}")
        
        # Only warn if neither factory nor router is configured
        if not self.factory_contract and not self.router_contract:
            logger.warning("Neither factory nor router available for price query")
        
        return None
    
    def _get_price_from_pair(
        self,
        token_in: str,
        token_out: str,
        token_in_decimals: int,
        token_out_decimals: int
    ) -> Optional[Decimal]:
        """
        Get price by querying pair contract directly.
        
        Uses factory to find pair, then queries reserves.
        
        Args:
            token_in: Address of input token
            token_out: Address of output token
            token_in_decimals: Decimals of input token
            token_out_decimals: Decimals of output token
            
        Returns:
            Price as Decimal (token_out / token_in), or None if unavailable
        """
        if not self.factory_contract:
            return None
        
        try:
            # Get pair address from factory
            token_in_checksum = Web3.to_checksum_address(token_in)
            token_out_checksum = Web3.to_checksum_address(token_out)
            
            # Try both orders (token0, token1) and (token1, token0)
            pair_address = self.factory_contract.functions.getPair(
                token_in_checksum,
                token_out_checksum
            ).call()
            
            if pair_address == "0x0000000000000000000000000000000000000000":
                logger.debug(f"No pair found for {token_in} / {token_out}")
                return None
            
            # Query pair reserves
            reserves_data = self.get_pair_reserves(pair_address)
            if not reserves_data:
                return None
            
            reserve0, reserve1, token0, token1 = reserves_data
            
            # Determine which token is which
            if token0.lower() == token_in_checksum.lower():
                # token_in is token0, token_out is token1
                # Price = reserve1 / reserve0 (adjusted for decimals)
                price = (Decimal(reserve1) / Decimal(10**token_out_decimals)) / (Decimal(reserve0) / Decimal(10**token_in_decimals))
            elif token1.lower() == token_in_checksum.lower():
                # token_in is token1, token_out is token0
                # Price = reserve0 / reserve1 (adjusted for decimals)
                price = (Decimal(reserve0) / Decimal(10**token_out_decimals)) / (Decimal(reserve1) / Decimal(10**token_in_decimals))
            else:
                logger.warning(f"Token mismatch in pair: expected {token_in} or {token_out}, got {token0} and {token1}")
                return None
            
            logger.debug(f"BlazeSwap price (pair): 1 {token_in} = {price:.8f} {token_out}")
            return price
            
        except Exception as e:
            logger.debug(f"Error getting price from pair: {e}")
            return None
    
    def get_pair_reserves(
        self,
        pair_address: str
    ) -> Optional[tuple]:
        """
        Get reserves directly from a pair contract.
        
        Args:
            pair_address: Address of the pair contract
            
        Returns:
            Tuple of (reserve0, reserve1, token0_address, token1_address) or None
        """
        try:
            pair_abi = fetch_abi_from_flarescan(pair_address, contract_name='blazeswap_pair')
            if not pair_abi:
                pair_abi = UNISWAP_V2_PAIR_ABI
            
            pair_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(pair_address),
                abi=pair_abi
            )
            
            reserves = pair_contract.functions.getReserves().call()
            token0 = pair_contract.functions.token0().call()
            token1 = pair_contract.functions.token1().call()
            
            return (reserves[0], reserves[1], token0, token1)
            
        except Exception as e:
            logger.error(f"Error getting pair reserves: {e}")
            return None

