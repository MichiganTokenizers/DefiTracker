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

# Uniswap V2 Pair ABI (minimal - for direct reserve queries)
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
    
    def __init__(self, web3: Web3, router_address: str):
        """
        Initialize BlazeSwap price feed.
        
        Args:
            web3: Web3 instance for Flare network
            router_address: BlazeSwap router contract address
        """
        self.web3 = web3
        self.router_address = router_address
        self.router_contract = None
        self._initialize_router()
    
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
        
        Args:
            token_in: Address of input token
            token_out: Address of output token
            token_in_decimals: Decimals of input token
            token_out_decimals: Decimals of output token
            amount_in: Amount of token_in (default: 1 token)
            
        Returns:
            Price as Decimal (amount_out / amount_in), or None if unavailable
        """
        if not self.router_contract:
            logger.error("Router contract not initialized")
            return None
        
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
                
                logger.debug(f"BlazeSwap price: {amount_in} {token_in} = {amount_out} {token_out} (price: {price})")
                return price
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting price from BlazeSwap: {e}")
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

