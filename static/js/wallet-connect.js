/**
 * Cardano Wallet Connection (CIP-30)
 * Supports Nami, Eternl, Flint, Lace, and other CIP-30 compatible wallets
 */

// Supported wallets
const SUPPORTED_WALLETS = [
    { id: 'nami', name: 'Nami' },
    { id: 'eternl', name: 'Eternl' },
    { id: 'flint', name: 'Flint' },
    { id: 'lace', name: 'Lace' },
    { id: 'yoroi', name: 'Yoroi' },
    { id: 'gerowallet', name: 'GeroWallet' },
    { id: 'typhoncip30', name: 'Typhon' },
    { id: 'nufi', name: 'NuFi' }
];

/**
 * Detect available CIP-30 wallets
 */
function getAvailableWallets() {
    if (typeof window.cardano === 'undefined') {
        return [];
    }
    
    return SUPPORTED_WALLETS.filter(wallet => {
        return window.cardano[wallet.id] !== undefined;
    });
}

/**
 * Convert hex string to bytes
 */
function hexToBytes(hex) {
    const bytes = [];
    for (let i = 0; i < hex.length; i += 2) {
        bytes.push(parseInt(hex.substr(i, 2), 16));
    }
    return new Uint8Array(bytes);
}

/**
 * Convert bytes to hex string
 */
function bytesToHex(bytes) {
    return Array.from(bytes)
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');
}

/**
 * Connect to a Cardano wallet and authenticate
 */
async function connectWallet() {
    const btn = document.getElementById('walletLoginBtn');
    const originalText = btn.innerHTML;
    
    try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Connecting...';
        
        // Check if Cardano wallets are available
        const availableWallets = getAvailableWallets();
        
        if (availableWallets.length === 0) {
            throw new Error('No Cardano wallet found. Please install Nami, Eternl, or another CIP-30 wallet.');
        }
        
        // If multiple wallets, let user choose (for now, just use the first one)
        // In a production app, you'd show a wallet selection modal
        let selectedWallet = availableWallets[0];
        
        // If there's more than one wallet, try to use the user's preferred one
        if (availableWallets.length > 1) {
            // Check for common preferences
            const preferredOrder = ['eternl', 'nami', 'lace', 'flint'];
            for (const pref of preferredOrder) {
                const found = availableWallets.find(w => w.id === pref);
                if (found) {
                    selectedWallet = found;
                    break;
                }
            }
        }
        
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Connecting to ${selectedWallet.name}...`;
        
        // Enable the wallet
        const api = await window.cardano[selectedWallet.id].enable();
        
        // Get wallet addresses
        const addresses = await api.getUsedAddresses();
        if (!addresses || addresses.length === 0) {
            throw new Error('No addresses found in wallet. Please use a wallet with funds.');
        }
        
        // Use the first address (in hex format from CIP-30)
        const addressHex = addresses[0];
        
        // Convert hex address to bech32 for display and storage
        // CIP-30 returns addresses in CBOR hex format
        // We need to decode this to get the actual address
        const walletAddress = await getAddressFromHex(api, addressHex);
        
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Requesting challenge...';
        
        // Request challenge from server
        const challengeResponse = await fetch('/api/auth/wallet-challenge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ wallet_address: walletAddress })
        });
        
        if (!challengeResponse.ok) {
            const error = await challengeResponse.json();
            throw new Error(error.error || 'Failed to get challenge');
        }
        
        const { nonce, message } = await challengeResponse.json();
        
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sign message in wallet...';
        
        // Sign the message using CIP-30 signData
        // Convert message to hex
        const messageHex = bytesToHex(new TextEncoder().encode(message));
        
        // signData returns { signature, key } in COSE format
        let signatureData;
        try {
            signatureData = await api.signData(addressHex, messageHex);
        } catch (signError) {
            if (signError.code === 2) {
                throw new Error('Signature request was declined');
            }
            throw signError;
        }
        
        // Extract signature and public key from COSE structure
        // The signData response is a COSE_Sign1 structure
        const { signature, key } = extractSignatureAndKey(signatureData);
        
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Verifying...';
        
        // Send to server for verification
        const loginResponse = await fetch('/api/auth/wallet-login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                wallet_address: walletAddress,
                signature: signature,
                public_key: key
            })
        });
        
        const loginData = await loginResponse.json();
        
        if (loginResponse.ok) {
            // Check if we should show the newsletter prompt
            if (loginData.show_email_prompt) {
                // Close auth modal first
                const authModal = bootstrap.Modal.getInstance(document.getElementById('authModal'));
                if (authModal) authModal.hide();
                
                // Show newsletter modal after a brief delay
                setTimeout(() => {
                    if (typeof showNewsletterModal === 'function') {
                        showNewsletterModal();
                    } else {
                        // Fallback: reload page
                        window.location.reload();
                    }
                }, 300);
            } else {
                // No prompt needed - reload page
                window.location.reload();
            }
        } else {
            throw new Error(loginData.error || 'Wallet login failed');
        }
        
    } catch (error) {
        console.error('Wallet connection error:', error);
        showAuthAlert(error.message || 'Failed to connect wallet');
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

/**
 * Get bech32 address from hex address
 * CIP-30 returns addresses in hex CBOR format
 */
async function getAddressFromHex(api, hexAddress) {
    // Try to get the network ID to determine address prefix
    try {
        // If it already looks like a bech32 address, use it
        if (hexAddress.startsWith('addr1') || hexAddress.startsWith('addr_test1')) {
            return hexAddress;
        }
        
        // The hex from CIP-30 is the raw address bytes
        // We'll use a simplified bech32-like identifier
        // The server accepts addr1 + hex as a valid identifier
        const networkId = await api.getNetworkId();
        const prefix = networkId === 0 ? 'addr_test1' : 'addr1';
        
        // Use the full hex as the identifier (this is unique per wallet)
        // Real bech32 encoding would require a proper library
        return `${prefix}${hexAddress}`;
        
    } catch (e) {
        console.warn('Could not get network ID:', e);
        // Default to mainnet prefix with hex
        return `addr1${hexAddress}`;
    }
}

/**
 * Extract signature and public key from CIP-30 signData response
 * The response is a COSE_Sign1 structure in hex
 */
function extractSignatureAndKey(signatureData) {
    // CIP-30 signData returns:
    // {
    //   signature: hex string of COSE_Sign1 structure
    //   key: hex string of COSE_Key structure
    // }
    
    // For Ed25519 signatures used by Cardano:
    // - The signature in COSE_Sign1 is 64 bytes
    // - The public key in COSE_Key is 32 bytes
    
    // Simplified extraction - in production, properly parse COSE structures
    let signature = signatureData.signature || signatureData;
    let key = signatureData.key || '';
    
    // If it's a string, it might be the raw signature
    if (typeof signatureData === 'string') {
        signature = signatureData;
    }
    
    // Try to extract the actual Ed25519 signature (last 64 bytes of COSE_Sign1)
    // and public key (32 bytes from COSE_Key)
    
    // The key structure contains the public key
    // For now, return as-is and let server handle parsing
    
    return {
        signature: signature,
        key: key
    };
}

// Export for use in other scripts if needed
window.WalletConnect = {
    getAvailableWallets,
    connectWallet
};

