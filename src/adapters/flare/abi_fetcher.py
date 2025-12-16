"""Utility to fetch contract ABIs from FlareScan"""
import requests
import logging
import json
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

FLARESCAN_API_URL = "https://api.flarescan.com/api"
ABIS_DIR = Path(__file__).parent.parent.parent.parent / "abis"

# Rate limiting: Free tier allows 2 requests per second
# Track last request time to enforce rate limit
_last_request_time = 0
_min_request_interval = 0.5  # 500ms = 2 requests per second


def _rate_limit():
    """Enforce rate limiting: 2 requests per second (free tier)"""
    global _last_request_time
    current_time = time.time()
    time_since_last = current_time - _last_request_time
    
    if time_since_last < _min_request_interval:
        sleep_time = _min_request_interval - time_since_last
        time.sleep(sleep_time)
    
    _last_request_time = time.time()


def load_abi_from_file(contract_name: str) -> Optional[Dict[str, Any]]:
    """
    Load ABI from local file if manually extracted.
    
    Args:
        contract_name: Name of contract (e.g., 'lens', 'comptroller')
        
    Returns:
        ABI as dict, or None if file doesn't exist
    """
    abi_file = ABIS_DIR / f"{contract_name.lower()}_abi.json"
    if abi_file.exists():
        try:
            with open(abi_file, 'r') as f:
                abi = json.load(f)
            logger.info(f"Loaded ABI from local file: {abi_file}")
            return abi
        except Exception as e:
            logger.warning(f"Error loading ABI from {abi_file}: {e}")
    return None


def fetch_abi_from_flarescan(contract_address: str, api_key: Optional[str] = None, contract_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch contract ABI from FlareScan API or local file.
    
    According to FlareScan documentation (etherscan-like API):
    https://flarescan.com/documentation/api/etherscan-like/contracts
    
    Free tier: 2 requests per second, 10,000 calls per day
    No API key required for free tier.
    
    Args:
        contract_address: Contract address to fetch ABI for
        api_key: Optional API key (not required for free tier)
        contract_name: Optional contract name for loading from local file (e.g., 'lens', 'comptroller')
        
    Returns:
        ABI as dict, or None if not available
    """
    # First, try loading from local file if contract_name provided
    if contract_name:
        local_abi = load_abi_from_file(contract_name)
        if local_abi:
            return local_abi
    
    # Enforce rate limiting: 2 requests per second
    _rate_limit()
    
    try:
        # Build URL - no API key needed for free tier
        url = f"{FLARESCAN_API_URL}?module=contract&action=getabi&address={contract_address}"
        if api_key:
            url += f"&apikey={api_key}"
        
        # Add headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == '1' and data.get('result'):
                abi_str = data['result']
                abi = json.loads(abi_str)
                logger.info(f"Successfully fetched ABI for contract {contract_address} ({len(abi)} items)")
                return abi
            else:
                logger.warning(f"Contract {contract_address} not verified: {data.get('message', 'Unknown')}")
                return None
        elif response.status_code == 403:
            # 403 might be rate limiting or IP blocking
            logger.warning(f"FlareScan API returned 403 - may be rate limited or IP blocked")
            logger.info("Free tier allows 2 requests/second, 10,000 calls/day")
            # Try fetching from contract page as fallback
            return _fetch_abi_from_contract_page(contract_address)
        elif response.status_code == 202:
            # 202 might indicate request queued
            logger.warning(f"FlareScan API returned 202 - request may be queued")
            # Wait a bit and try contract page
            time.sleep(1)
            return _fetch_abi_from_contract_page(contract_address)
        else:
            logger.warning(f"FlareScan API returned status {response.status_code}")
            if response.status_code == 200:
                # Even with 200, check if we got valid data
                try:
                    data = response.json()
                    logger.debug(f"API response: {data}")
                except:
                    pass
            return None
            
    except Exception as e:
        logger.error(f"Error fetching ABI from FlareScan for {contract_address}: {e}")
        # Try fetching from contract page as fallback
        return _fetch_abi_from_contract_page(contract_address)


def _fetch_abi_from_contract_page(contract_address: str) -> Optional[Dict[str, Any]]:
    """
    Fallback: Try to extract ABI from FlareScan contract verification page.
    
    This is a workaround if the API requires authentication or is blocked.
    Users can manually copy the ABI from the contract page if needed.
    
    Args:
        contract_address: Contract address
        
    Returns:
        ABI as dict, or None if extraction fails
    """
    try:
        url = f"https://flarescan.com/address/{contract_address}#code"
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Try to find ABI JSON in the page (some explorers embed it)
            # This is a basic attempt - may need more sophisticated parsing
            content = response.text
            # Look for JSON-like ABI patterns
            abi_pattern = r'"abi"\s*:\s*(\[[^\]]+\])'
            match = re.search(abi_pattern, content)
            if match:
                try:
                    abi = json.loads(match.group(1))
                    logger.info(f"Extracted ABI from contract page for {contract_address}")
                    return abi
                except json.JSONDecodeError:
                    pass
        
        logger.info(f"Contract page available at: {url}")
        logger.info("If contract is verified, you can manually copy the ABI from the page")
        return None
        
    except Exception as e:
        logger.debug(f"Could not fetch from contract page: {e}")
        return None


def get_minimal_comptroller_abi() -> list:
    """
    Return minimal ABI for Comptroller contract.
    The Comptroller manages markets and provides rate information.
    """
    return [
        {
            "constant": True,
            "inputs": [{"internalType": "address", "name": "cToken", "type": "address"}],
            "name": "getMarketData",
            "outputs": [
                {"internalType": "uint256", "name": "supplyRatePerBlock", "type": "uint256"},
                {"internalType": "uint256", "name": "borrowRatePerBlock", "type": "uint256"},
                {"internalType": "uint256", "name": "totalSupply", "type": "uint256"},
                {"internalType": "uint256", "name": "totalBorrows", "type": "uint256"},
                {"internalType": "uint256", "name": "exchangeRate", "type": "uint256"}
            ],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [{"internalType": "address", "name": "cToken", "type": "address"}],
            "name": "supplyRatePerBlock",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        }
    ]


def get_minimal_lens_abi() -> list:
    """
    Return minimal ABI for Lens contract with common functions.
    This is a fallback if we can't fetch the full ABI.
    """
    return [
        {
            "constant": True,
            "inputs": [{"name": "cToken", "type": "address"}],
            "name": "getMarketData",
            "outputs": [
                {"name": "supplyRatePerBlock", "type": "uint256"},
                {"name": "borrowRatePerBlock", "type": "uint256"},
                {"name": "totalSupply", "type": "uint256"},
                {"name": "totalBorrows", "type": "uint256"},
                {"name": "exchangeRate", "type": "uint256"}
            ],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [{"name": "cToken", "type": "address"}],
            "name": "supplyRatePerBlock",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        }
    ]


def get_minimal_ctoken_abi() -> list:
    """
    Return minimal ABI for cToken (ISO market) contracts.
    Based on standard Compound cToken interface.
    This is a fallback if we can't fetch the full ABI.
    """
    return [
        {
            "constant": True,
            "inputs": [],
            "name": "supplyRatePerBlock",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "borrowRatePerBlock",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "totalSupply",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "totalBorrows",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "exchangeRateStored",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "getCash",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": False, "internalType": "address", "name": "minter", "type": "address"},
                {"indexed": False, "internalType": "uint256", "name": "mintAmount", "type": "uint256"},
                {"indexed": False, "internalType": "uint256", "name": "mintTokens", "type": "uint256"}
            ],
            "name": "Mint",
            "type": "event"
        }
    ]

