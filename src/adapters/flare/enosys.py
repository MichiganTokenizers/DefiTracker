"""
Enosys DEX V3 Protocol Adapter for Flare blockchain.

Enosys is a Uniswap V3-style concentrated liquidity DEX on Flare.
Key features:
- NFT-based LP positions with custom price ranges
- 6-hour epochs for incentive distribution
- Fees proportional to active liquidity during swaps

This adapter queries:
- Pool state (current tick, liquidity, TVL)
- Individual NFT positions (range, liquidity, fees)
- Position analysis (range width, in-range status)
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from web3 import Web3

from src.adapters.base import ProtocolAdapter

logger = logging.getLogger(__name__)


# ============================================
# Data Classes
# ============================================

@dataclass
class EnosysPoolState:
    """Current state of an Enosys V3 pool."""
    pool_address: str
    token0_symbol: str
    token1_symbol: str
    fee_tier: int  # basis points (e.g., 3000 = 0.3%)
    
    # Pool state
    current_tick: int = 0
    sqrt_price_x96: int = 0
    liquidity: int = 0
    
    # TVL
    tvl_token0: Optional[Decimal] = None
    tvl_token1: Optional[Decimal] = None
    tvl_usd: Optional[Decimal] = None
    
    # Volume/fees
    volume_24h_usd: Optional[Decimal] = None
    fees_24h_usd: Optional[Decimal] = None
    
    # Position counts
    total_positions: int = 0
    active_positions: int = 0
    
    # Epoch incentives
    epoch_number: Optional[int] = None
    epoch_incentives: Optional[Decimal] = None
    incentive_token_symbol: str = "WFLR"


@dataclass
class EnosysPosition:
    """Individual NFT LP position data."""
    token_id: int
    owner_address: str
    pool_address: str
    
    # Range bounds
    tick_lower: int
    tick_upper: int
    
    # Position liquidity
    liquidity: int
    
    # Token amounts
    amount0: Optional[Decimal] = None
    amount1: Optional[Decimal] = None
    amount_usd: Optional[Decimal] = None
    
    # Uncollected fees
    fees_token0: Optional[Decimal] = None
    fees_token1: Optional[Decimal] = None
    fees_usd: Optional[Decimal] = None
    
    # Computed metrics
    is_in_range: bool = False
    range_width_ticks: int = 0
    range_width_percent: Optional[Decimal] = None
    range_category: str = "wide"  # narrow, medium, wide
    
    # APR metrics
    fees_24h_usd: Optional[Decimal] = None
    fee_apr: Optional[Decimal] = None
    time_in_range_pct: Optional[Decimal] = None
    incentive_share: Optional[Decimal] = None
    incentive_apr: Optional[Decimal] = None
    total_apr: Optional[Decimal] = None
    
    # Reference
    epoch_number: Optional[int] = None


@dataclass
class EnosysPoolMetrics:
    """Aggregated pool metrics for APR display."""
    pool_address: str
    pair: str
    fee_tier: int
    tvl_usd: Optional[Decimal] = None
    volume_24h_usd: Optional[Decimal] = None
    fees_24h_usd: Optional[Decimal] = None
    
    # APR by range category
    narrow_avg_apr: Optional[Decimal] = None
    medium_avg_apr: Optional[Decimal] = None
    wide_avg_apr: Optional[Decimal] = None
    pool_avg_apr: Optional[Decimal] = None
    
    # Position distribution
    narrow_positions: int = 0
    medium_positions: int = 0
    wide_positions: int = 0
    total_positions: int = 0
    active_positions: int = 0


# ============================================
# ABI Definitions (Uniswap V3 Compatible)
# ============================================

# Minimal Factory ABI
FACTORY_ABI = [
    {
        "inputs": [
            {"type": "address", "name": "tokenA"},
            {"type": "address", "name": "tokenB"},
            {"type": "uint24", "name": "fee"}
        ],
        "name": "getPool",
        "outputs": [{"type": "address", "name": "pool"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Minimal Pool ABI
POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"type": "uint160", "name": "sqrtPriceX96"},
            {"type": "int24", "name": "tick"},
            {"type": "uint16", "name": "observationIndex"},
            {"type": "uint16", "name": "observationCardinality"},
            {"type": "uint16", "name": "observationCardinalityNext"},
            {"type": "uint8", "name": "feeProtocol"},
            {"type": "bool", "name": "unlocked"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "liquidity",
        "outputs": [{"type": "uint128", "name": ""}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"type": "address", "name": ""}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"type": "address", "name": ""}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "fee",
        "outputs": [{"type": "uint24", "name": ""}],
        "stateMutability": "view",
        "type": "function"
    }
]

# NonfungiblePositionManager ABI (for NFT positions)
POSITION_MANAGER_ABI = [
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"type": "uint256", "name": ""}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"type": "uint256", "name": "tokenId"}],
        "name": "positions",
        "outputs": [
            {"type": "uint96", "name": "nonce"},
            {"type": "address", "name": "operator"},
            {"type": "address", "name": "token0"},
            {"type": "address", "name": "token1"},
            {"type": "uint24", "name": "fee"},
            {"type": "int24", "name": "tickLower"},
            {"type": "int24", "name": "tickUpper"},
            {"type": "uint128", "name": "liquidity"},
            {"type": "uint256", "name": "feeGrowthInside0LastX128"},
            {"type": "uint256", "name": "feeGrowthInside1LastX128"},
            {"type": "uint128", "name": "tokensOwed0"},
            {"type": "uint128", "name": "tokensOwed1"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"type": "uint256", "name": "tokenId"}],
        "name": "ownerOf",
        "outputs": [{"type": "address", "name": ""}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"type": "uint256", "name": "index"}],
        "name": "tokenByIndex",
        "outputs": [{"type": "uint256", "name": ""}],
        "stateMutability": "view",
        "type": "function"
    }
]

# ERC20 ABI for token info
ERC20_ABI = [
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"type": "string", "name": ""}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"type": "uint8", "name": ""}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"type": "address", "name": "account"}],
        "name": "balanceOf",
        "outputs": [{"type": "uint256", "name": ""}],
        "stateMutability": "view",
        "type": "function"
    }
]


class EnosysAdapter(ProtocolAdapter):
    """
    Adapter for Enosys DEX V3 on Flare blockchain.
    
    Provides methods to:
    - Query pool state and TVL
    - Fetch individual NFT positions
    - Analyze position ranges and categorize them
    - Calculate fee and incentive APRs by range category
    """
    
    # Tick spacing by fee tier (standard Uniswap V3 values)
    TICK_SPACING = {
        100: 1,      # 0.01% fee
        500: 10,     # 0.05% fee
        3000: 60,    # 0.3% fee
        10000: 200   # 1% fee
    }
    
    def __init__(self, protocol_name: str, config: Dict):
        super().__init__(protocol_name, config)
        
        # Contract addresses
        self.factory_address = config.get('factory', '')
        self.position_manager_address = config.get('position_manager', '')
        self.quoter_address = config.get('quoter', '')
        self.incentive_controller_address = config.get('incentive_controller', '')
        
        # Incentive token config
        incentive_config = config.get('incentive_token', {})
        self.incentive_token_symbol = incentive_config.get('symbol', 'WFLR')
        self.incentive_token_address = incentive_config.get('address', '')
        self.incentive_token_decimals = incentive_config.get('decimals', 18)
        
        # Configuration
        self.epoch_duration_hours = config.get('epoch_duration_hours', 6)
        self.timeout = config.get('timeout', 30)
        self.max_retries = config.get('max_retries', 3)
        self.cache_ttl = config.get('cache_ttl', 300)
        self.min_tvl_usd = config.get('min_tvl_usd', 1000)
        
        # Range category thresholds
        range_config = config.get('range_categories', {})
        self.narrow_max_pct = Decimal(str(range_config.get('narrow_max_pct', 1.0)))
        self.medium_max_pct = Decimal(str(range_config.get('medium_max_pct', 5.0)))
        
        # Configured pools
        self.pools_config = config.get('pools', [])
        
        # Web3 instance (set by chain adapter)
        self.web3: Optional[Web3] = None
        
        # Contract instances (initialized lazily)
        self._factory_contract = None
        self._position_manager_contract = None
        
        # Token cache (address -> {symbol, decimals})
        self._token_cache: Dict[str, Dict] = {}
        
        # Pool cache
        self._pool_cache: Dict[str, EnosysPoolState] = {}
    
    def set_web3_instance(self, web3: Web3):
        """Set Web3 instance from chain adapter."""
        self.web3 = web3
    
    def get_supported_assets(self) -> List[str]:
        """Get list of configured pool pair names."""
        return [p.get('symbol', p.get('name', '')) for p in self.pools_config]
    
    def get_supply_apr(self, asset: str) -> Optional[Decimal]:
        """
        Get average APR for a pool (across all position ranges).
        
        Args:
            asset: Pool pair name (e.g., "WFLR-eUSDT")
            
        Returns:
            Average APR as Decimal percentage, or None if unavailable
        """
        metrics = self.get_pool_metrics(asset)
        if metrics:
            return metrics.pool_avg_apr
        return None
    
    def compute_apr_from_onchain(self, asset: str, lookback_days: int = 7) -> Optional[Decimal]:
        """On-chain APR computation for concentrated liquidity."""
        # For V3-style pools, APR varies by position range
        # This would require historical position tracking
        logger.info("On-chain APR computation for Enosys requires historical data (asset=%s)", asset)
        return None
    
    # ============================================
    # Pool State Methods
    # ============================================
    
    def get_pool_state(self, pool_address: str) -> Optional[EnosysPoolState]:
        """
        Get current state of a pool.
        
        Args:
            pool_address: Pool contract address
            
        Returns:
            EnosysPoolState or None if query fails
        """
        if not self.web3 or not pool_address:
            logger.warning("Web3 not configured or pool address empty")
            return None
        
        try:
            pool_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=POOL_ABI
            )
            
            # Get pool state from slot0
            slot0 = pool_contract.functions.slot0().call()
            sqrt_price_x96 = slot0[0]
            current_tick = slot0[1]
            
            # Get total liquidity
            liquidity = pool_contract.functions.liquidity().call()
            
            # Get token addresses
            token0_address = pool_contract.functions.token0().call()
            token1_address = pool_contract.functions.token1().call()
            fee_tier = pool_contract.functions.fee().call()
            
            # Get token info
            token0_info = self._get_token_info(token0_address)
            token1_info = self._get_token_info(token1_address)
            
            # Calculate TVL
            tvl_token0, tvl_token1 = self._get_pool_tvl(
                pool_address, token0_address, token1_address,
                token0_info.get('decimals', 18), token1_info.get('decimals', 18)
            )
            
            pool_state = EnosysPoolState(
                pool_address=pool_address,
                token0_symbol=token0_info.get('symbol', 'TOKEN0'),
                token1_symbol=token1_info.get('symbol', 'TOKEN1'),
                fee_tier=fee_tier,
                current_tick=current_tick,
                sqrt_price_x96=sqrt_price_x96,
                liquidity=liquidity,
                tvl_token0=tvl_token0,
                tvl_token1=tvl_token1
            )
            
            logger.debug(
                "Pool %s state: tick=%d, liquidity=%d, TVL=(%s, %s)",
                pool_address[:10], current_tick, liquidity, tvl_token0, tvl_token1
            )
            
            return pool_state
            
        except Exception as e:
            logger.error("Error fetching pool state for %s: %s", pool_address, e)
            return None
    
    def _get_token_info(self, token_address: str) -> Dict:
        """Get token symbol and decimals, with caching."""
        if token_address in self._token_cache:
            return self._token_cache[token_address]
        
        try:
            token_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=ERC20_ABI
            )
            
            symbol = token_contract.functions.symbol().call()
            decimals = token_contract.functions.decimals().call()
            
            info = {'symbol': symbol, 'decimals': decimals, 'address': token_address}
            self._token_cache[token_address] = info
            return info
            
        except Exception as e:
            logger.warning("Error fetching token info for %s: %s", token_address, e)
            return {'symbol': 'UNKNOWN', 'decimals': 18, 'address': token_address}
    
    def _get_pool_tvl(
        self, 
        pool_address: str, 
        token0_address: str, 
        token1_address: str,
        decimals0: int,
        decimals1: int
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """Get pool TVL by checking token balances in the pool contract."""
        try:
            token0_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token0_address),
                abi=ERC20_ABI
            )
            token1_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token1_address),
                abi=ERC20_ABI
            )
            
            balance0 = token0_contract.functions.balanceOf(
                Web3.to_checksum_address(pool_address)
            ).call()
            balance1 = token1_contract.functions.balanceOf(
                Web3.to_checksum_address(pool_address)
            ).call()
            
            tvl_token0 = Decimal(balance0) / Decimal(10 ** decimals0)
            tvl_token1 = Decimal(balance1) / Decimal(10 ** decimals1)
            
            return tvl_token0, tvl_token1
            
        except Exception as e:
            logger.warning("Error fetching pool TVL: %s", e)
            return None, None
    
    # ============================================
    # Position Methods
    # ============================================
    
    def get_position(self, token_id: int) -> Optional[EnosysPosition]:
        """
        Get a single NFT position by token ID.
        
        Args:
            token_id: NFT token ID
            
        Returns:
            EnosysPosition or None if not found
        """
        if not self.web3 or not self.position_manager_address:
            logger.warning("Web3 or position manager address not configured")
            return None
        
        try:
            pm_contract = self._get_position_manager_contract()
            
            # Get position data
            position_data = pm_contract.functions.positions(token_id).call()
            
            # Unpack position tuple
            (nonce, operator, token0, token1, fee, tick_lower, tick_upper,
             liquidity, fee_growth0, fee_growth1, tokens_owed0, tokens_owed1) = position_data
            
            # Skip positions with no liquidity
            if liquidity == 0:
                return None
            
            # Get owner
            owner = pm_contract.functions.ownerOf(token_id).call()
            
            # Get token info
            token0_info = self._get_token_info(token0)
            token1_info = self._get_token_info(token1)
            
            # Find pool address
            pool_address = self._get_pool_address(token0, token1, fee)
            
            # Get pool state for in-range check
            pool_state = self.get_pool_state(pool_address) if pool_address else None
            current_tick = pool_state.current_tick if pool_state else 0
            
            # Check if in range
            is_in_range = tick_lower <= current_tick < tick_upper
            
            # Calculate range width
            range_width_ticks = tick_upper - tick_lower
            range_width_percent = self._ticks_to_percent(range_width_ticks)
            range_category = self._categorize_range(range_width_percent)
            
            # Convert owed fees to decimal
            fees_token0 = Decimal(tokens_owed0) / Decimal(10 ** token0_info['decimals'])
            fees_token1 = Decimal(tokens_owed1) / Decimal(10 ** token1_info['decimals'])
            
            position = EnosysPosition(
                token_id=token_id,
                owner_address=owner,
                pool_address=pool_address or '',
                tick_lower=tick_lower,
                tick_upper=tick_upper,
                liquidity=liquidity,
                fees_token0=fees_token0,
                fees_token1=fees_token1,
                is_in_range=is_in_range,
                range_width_ticks=range_width_ticks,
                range_width_percent=range_width_percent,
                range_category=range_category
            )
            
            logger.debug(
                "Position %d: range=[%d,%d], width=%.2f%%, category=%s, in_range=%s",
                token_id, tick_lower, tick_upper, range_width_percent, range_category, is_in_range
            )
            
            return position
            
        except Exception as e:
            logger.error("Error fetching position %d: %s", token_id, e)
            return None
    
    def get_positions_for_pool(
        self, 
        pool_address: str,
        max_positions: int = 1000
    ) -> List[EnosysPosition]:
        """
        Get all positions for a specific pool.
        
        Args:
            pool_address: Pool contract address
            max_positions: Maximum positions to fetch (for safety)
            
        Returns:
            List of EnosysPosition objects
        """
        if not self.web3 or not self.position_manager_address:
            logger.warning("Web3 or position manager address not configured")
            return []
        
        positions = []
        pm_contract = self._get_position_manager_contract()
        
        try:
            # Get total supply of NFT positions
            total_supply = pm_contract.functions.totalSupply().call()
            logger.info("Total NFT positions: %d", total_supply)
            
            # Iterate through positions (this can be slow for large collections)
            pool_address_lower = pool_address.lower()
            
            for i in range(min(total_supply, max_positions)):
                try:
                    # Get token ID at index
                    token_id = pm_contract.functions.tokenByIndex(i).call()
                    
                    # Get position details
                    position = self.get_position(token_id)
                    
                    if position and position.pool_address.lower() == pool_address_lower:
                        positions.append(position)
                        
                except Exception as e:
                    logger.debug("Error fetching position at index %d: %s", i, e)
                    continue
            
            logger.info("Found %d positions for pool %s", len(positions), pool_address[:10])
            return positions
            
        except Exception as e:
            logger.error("Error fetching positions for pool %s: %s", pool_address, e)
            return positions
    
    def _get_position_manager_contract(self):
        """Get or create position manager contract instance."""
        if self._position_manager_contract is None:
            self._position_manager_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(self.position_manager_address),
                abi=POSITION_MANAGER_ABI
            )
        return self._position_manager_contract
    
    def _get_pool_address(self, token0: str, token1: str, fee: int) -> Optional[str]:
        """Get pool address from factory."""
        if not self.factory_address:
            return None
        
        try:
            factory_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(self.factory_address),
                abi=FACTORY_ABI
            )
            
            pool_address = factory_contract.functions.getPool(
                Web3.to_checksum_address(token0),
                Web3.to_checksum_address(token1),
                fee
            ).call()
            
            return pool_address if pool_address != '0x' + '0' * 40 else None
            
        except Exception as e:
            logger.warning("Error getting pool address: %s", e)
            return None
    
    # ============================================
    # Range Analysis Methods
    # ============================================
    
    def _ticks_to_percent(self, tick_range: int) -> Decimal:
        """
        Convert tick range to percentage price range.
        
        In Uniswap V3, price = 1.0001^tick
        So price range = 1.0001^tick_upper / 1.0001^tick_lower = 1.0001^(tick_upper - tick_lower)
        """
        if tick_range <= 0:
            return Decimal(0)
        
        # Price ratio = 1.0001^tick_range
        price_ratio = Decimal(str(1.0001 ** tick_range))
        
        # Convert to percentage: (ratio - 1) * 100
        return (price_ratio - 1) * 100
    
    def _categorize_range(self, range_percent: Decimal) -> str:
        """
        Categorize range width into narrow/medium/wide.
        
        Args:
            range_percent: Range width as percentage
            
        Returns:
            Category string: 'narrow', 'medium', or 'wide'
        """
        if range_percent < self.narrow_max_pct:
            return 'narrow'
        elif range_percent < self.medium_max_pct:
            return 'medium'
        else:
            return 'wide'
    
    def analyze_positions_by_range(
        self, 
        positions: List[EnosysPosition]
    ) -> Dict[str, List[EnosysPosition]]:
        """
        Group positions by range category.
        
        Args:
            positions: List of positions to analyze
            
        Returns:
            Dict mapping category -> list of positions
        """
        result = {
            'narrow': [],
            'medium': [],
            'wide': []
        }
        
        for pos in positions:
            category = pos.range_category
            if category in result:
                result[category].append(pos)
        
        return result
    
    def calculate_range_apr_stats(
        self, 
        positions_by_range: Dict[str, List[EnosysPosition]]
    ) -> Dict[str, Dict]:
        """
        Calculate APR statistics by range category.
        
        Args:
            positions_by_range: Positions grouped by range category
            
        Returns:
            Dict with stats per category
        """
        stats = {}
        
        for category, positions in positions_by_range.items():
            if not positions:
                stats[category] = {
                    'count': 0,
                    'active_count': 0,
                    'avg_apr': None,
                    'avg_fee_apr': None,
                    'avg_incentive_apr': None,
                    'total_tvl_usd': Decimal(0),
                    'avg_range_width': Decimal(0)
                }
                continue
            
            active_count = sum(1 for p in positions if p.is_in_range)
            
            # Calculate averages (only for positions with APR data)
            aprs = [p.total_apr for p in positions if p.total_apr is not None]
            fee_aprs = [p.fee_apr for p in positions if p.fee_apr is not None]
            incentive_aprs = [p.incentive_apr for p in positions if p.incentive_apr is not None]
            
            avg_apr = sum(aprs) / len(aprs) if aprs else None
            avg_fee_apr = sum(fee_aprs) / len(fee_aprs) if fee_aprs else None
            avg_incentive_apr = sum(incentive_aprs) / len(incentive_aprs) if incentive_aprs else None
            
            total_tvl = sum(p.amount_usd or Decimal(0) for p in positions)
            avg_range_width = sum(p.range_width_percent or Decimal(0) for p in positions) / len(positions)
            
            stats[category] = {
                'count': len(positions),
                'active_count': active_count,
                'active_pct': (active_count / len(positions) * 100) if positions else 0,
                'avg_apr': avg_apr,
                'avg_fee_apr': avg_fee_apr,
                'avg_incentive_apr': avg_incentive_apr,
                'total_tvl_usd': total_tvl,
                'avg_range_width': avg_range_width
            }
        
        return stats
    
    # ============================================
    # Pool Metrics
    # ============================================
    
    def get_pool_metrics(self, pair_name: str) -> Optional[EnosysPoolMetrics]:
        """
        Get aggregated metrics for a pool including APR by range category.
        
        Args:
            pair_name: Pool pair name from config
            
        Returns:
            EnosysPoolMetrics or None
        """
        # Find pool config
        pool_config = None
        for p in self.pools_config:
            if p.get('symbol') == pair_name or p.get('name') == pair_name:
                pool_config = p
                break
        
        if not pool_config:
            logger.warning("Pool %s not found in configuration", pair_name)
            return None
        
        pool_address = pool_config.get('address', '')
        if not pool_address:
            logger.warning("Pool address not configured for %s", pair_name)
            return None
        
        # Get pool state
        pool_state = self.get_pool_state(pool_address)
        if not pool_state:
            return None
        
        # Get positions for this pool
        positions = self.get_positions_for_pool(pool_address)
        
        # Analyze by range
        positions_by_range = self.analyze_positions_by_range(positions)
        range_stats = self.calculate_range_apr_stats(positions_by_range)
        
        # Calculate overall pool APR (weighted by TVL if available)
        all_aprs = [p.total_apr for p in positions if p.total_apr is not None]
        pool_avg_apr = sum(all_aprs) / len(all_aprs) if all_aprs else None
        
        metrics = EnosysPoolMetrics(
            pool_address=pool_address,
            pair=pair_name,
            fee_tier=pool_state.fee_tier,
            tvl_usd=pool_state.tvl_usd,
            volume_24h_usd=pool_state.volume_24h_usd,
            fees_24h_usd=pool_state.fees_24h_usd,
            narrow_avg_apr=range_stats['narrow'].get('avg_apr'),
            medium_avg_apr=range_stats['medium'].get('avg_apr'),
            wide_avg_apr=range_stats['wide'].get('avg_apr'),
            pool_avg_apr=pool_avg_apr,
            narrow_positions=range_stats['narrow'].get('count', 0),
            medium_positions=range_stats['medium'].get('count', 0),
            wide_positions=range_stats['wide'].get('count', 0),
            total_positions=len(positions),
            active_positions=sum(1 for p in positions if p.is_in_range)
        )
        
        return metrics
    
    def get_all_pool_metrics(self) -> List[EnosysPoolMetrics]:
        """Get metrics for all configured pools."""
        metrics = []
        for pool_config in self.pools_config:
            pair_name = pool_config.get('symbol', pool_config.get('name', ''))
            if pair_name:
                pool_metrics = self.get_pool_metrics(pair_name)
                if pool_metrics:
                    metrics.append(pool_metrics)
        return metrics

