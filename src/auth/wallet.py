"""Cardano wallet authentication using CIP-30 signature verification"""
import secrets
import hashlib
from typing import Optional, Tuple
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
import binascii


def generate_nonce() -> str:
    """Generate a random nonce for wallet authentication challenge"""
    return secrets.token_hex(32)


def create_sign_message(nonce: str) -> str:
    """Create the message that the wallet should sign"""
    return f"Sign this message to authenticate with YieldLife.\n\nNonce: {nonce}"


def hex_to_bytes(hex_string: str) -> bytes:
    """Convert hex string to bytes, handling 0x prefix"""
    if hex_string.startswith('0x'):
        hex_string = hex_string[2:]
    return binascii.unhexlify(hex_string)


def verify_cardano_signature(
    message: str,
    signature_hex: str,
    public_key_hex: str
) -> bool:
    """
    Verify a Cardano wallet signature (Ed25519).
    
    CIP-30 signData returns a COSE_Sign1 structure. The frontend should extract:
    - The signature (Ed25519 signature bytes)
    - The public key (from the COSE_Key or derived from address)
    
    Args:
        message: The original message that was signed
        signature_hex: The Ed25519 signature in hex
        public_key_hex: The Ed25519 public key in hex
        
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Convert hex to bytes
        signature = hex_to_bytes(signature_hex)
        public_key = hex_to_bytes(public_key_hex)
        
        # Ed25519 public key should be 32 bytes
        if len(public_key) != 32:
            return False
            
        # Ed25519 signature should be 64 bytes
        if len(signature) != 64:
            return False
        
        # Create verify key from public key bytes
        verify_key = VerifyKey(public_key)
        
        # The message needs to be encoded as bytes
        message_bytes = message.encode('utf-8')
        
        # Verify the signature
        # In CIP-30, the signed data is typically hashed first
        # We'll try both raw message and hashed message
        try:
            verify_key.verify(message_bytes, signature)
            return True
        except BadSignatureError:
            # Try with SHA-256 hash of message (some wallets do this)
            message_hash = hashlib.sha256(message_bytes).digest()
            try:
                verify_key.verify(message_hash, signature)
                return True
            except BadSignatureError:
                return False
                
    except (binascii.Error, ValueError, Exception) as e:
        print(f"Signature verification error: {e}")
        return False


def extract_stake_key_hash(address: str) -> Optional[str]:
    """
    Extract the stake key hash from a Cardano address.
    This can be used as a more stable identifier than the full address.
    
    For now, we just use the full address as the identifier.
    """
    # TODO: Implement proper Cardano address parsing if needed
    return None


def validate_cardano_address(address: str) -> bool:
    """
    Validate that a string is a valid Cardano address identifier.
    
    We accept both:
    - Standard bech32 addresses (addr1...)
    - Hex-based identifiers (addr1 + hex bytes from CIP-30)
    
    Args:
        address: The address to validate
        
    Returns:
        True if valid Cardano address, False otherwise
    """
    if not address:
        return False
    
    # Cardano mainnet addresses start with 'addr1'
    # Testnet addresses start with 'addr_test1'
    valid_prefixes = ('addr1', 'addr_test1')
    
    if not address.startswith(valid_prefixes):
        return False
    
    # Basic length check
    # - Standard bech32: 58-108 characters
    # - Hex-based from CIP-30: can be longer (addr1 + 114 hex chars = ~120+)
    if len(address) < 50 or len(address) > 200:
        return False
    
    # Check for valid characters (bech32 + hex)
    # bech32 uses: 0-9, a-z except b, i, o (we're lenient here)
    # hex uses: 0-9, a-f
    valid_chars = set('0123456789abcdefghjklmnpqrstuvwxyz_')
    
    # Get the part after the prefix
    if address.startswith('addr_test1'):
        suffix = address[10:].lower()
    else:
        suffix = address[5:].lower()
    
    address_chars = set(suffix)
    
    if not address_chars.issubset(valid_chars):
        return False
    
    return True

