"""Utility to fetch contract ABIs from FlareScan"""
import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

FLARESCAN_API_URL = "https://api.flarescan.com/api"


def fetch_abi_from_flarescan(contract_address: str) -> Optional[Dict[str, Any]]:
    """
    Fetch contract ABI from FlareScan API.
    
    Args:
        contract_address: Contract address to fetch ABI for
        
    Returns:
        ABI as dict, or None if not available
    """
    try:
        url = f"{FLARESCAN_API_URL}?module=contract&action=getabi&address={contract_address}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == '1' and data.get('result'):
                abi_str = data['result']
                import json
                abi = json.loads(abi_str)
                logger.info(f"Successfully fetched ABI for contract {contract_address}")
                return abi
            else:
                logger.warning(f"Contract {contract_address} not verified on FlareScan")
                return None
        else:
            logger.warning(f"FlareScan API returned status {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching ABI from FlareScan for {contract_address}: {e}")
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

