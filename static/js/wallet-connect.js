/**
 * Cardano Wallet Connection (CIP-30)
 * Supports Nami, Eternl, Flint, Lace, and other CIP-30 compatible wallets
 */

// Supported wallets with icons (fetched via scripts/fetch_protocol_icons.py --wallets)
const SUPPORTED_WALLETS = [
    { id: 'nami', name: 'Nami', icon: '/static/wallet-nami-logo.png' },
    { id: 'eternl', name: 'Eternl', icon: '/static/wallet-eternl-logo.png' },
    { id: 'flint', name: 'Flint', icon: '/static/cardano-logo-blue.svg' },
    { id: 'lace', name: 'Lace', icon: '/static/wallet-lace-logo.png' },
    { id: 'yoroi', name: 'Yoroi', icon: '/static/wallet-yoroi-logo.png' },
    { id: 'begin', name: 'Begin', icon: '/static/wallet-begin-logo.png' },
    { id: 'gerowallet', name: 'GeroWallet', icon: '/static/wallet-gerowallet-logo.png' },
    { id: 'typhoncip30', name: 'Typhon', icon: '/static/wallet-typhon-logo.png' },
    { id: 'nufi', name: 'NuFi', icon: '/static/wallet-nufi-logo.png' }
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
 * Safely parse JSON response, handling HTML error pages
 */
async function safeJsonParse(response) {
    const text = await response.text();
    try {
        return JSON.parse(text);
    } catch (e) {
        // Server returned HTML instead of JSON (likely an error page)
        console.error('Server returned non-JSON response:', text.substring(0, 200));
        throw new Error(`Server error (${response.status}): ${response.statusText || 'Unable to process request'}`);
    }
}

/**
 * Bech32 encoding implementation for Cardano addresses
 */
const BECH32_CHARSET = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l';

function bech32Polymod(values) {
    const GEN = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3];
    let chk = 1;
    for (const v of values) {
        const b = chk >> 25;
        chk = ((chk & 0x1ffffff) << 5) ^ v;
        for (let i = 0; i < 5; i++) {
            if ((b >> i) & 1) {
                chk ^= GEN[i];
            }
        }
    }
    return chk;
}

function bech32HrpExpand(hrp) {
    const ret = [];
    for (let i = 0; i < hrp.length; i++) {
        ret.push(hrp.charCodeAt(i) >> 5);
    }
    ret.push(0);
    for (let i = 0; i < hrp.length; i++) {
        ret.push(hrp.charCodeAt(i) & 31);
    }
    return ret;
}

function bech32CreateChecksum(hrp, data) {
    const values = bech32HrpExpand(hrp).concat(data).concat([0, 0, 0, 0, 0, 0]);
    const polymod = bech32Polymod(values) ^ 1;
    const ret = [];
    for (let i = 0; i < 6; i++) {
        ret.push((polymod >> (5 * (5 - i))) & 31);
    }
    return ret;
}

function convertBits(data, fromBits, toBits, pad) {
    let acc = 0;
    let bits = 0;
    const ret = [];
    const maxv = (1 << toBits) - 1;

    for (const value of data) {
        acc = (acc << fromBits) | value;
        bits += fromBits;
        while (bits >= toBits) {
            bits -= toBits;
            ret.push((acc >> bits) & maxv);
        }
    }

    if (pad) {
        if (bits > 0) {
            ret.push((acc << (toBits - bits)) & maxv);
        }
    }

    return ret;
}

function bech32Encode(hrp, data) {
    const combined = data.concat(bech32CreateChecksum(hrp, data));
    let ret = hrp + '1';
    for (const d of combined) {
        ret += BECH32_CHARSET[d];
    }
    return ret;
}

/**
 * Convert hex address bytes to bech32 Cardano address
 */
function hexToBech32Address(hexAddress, networkId) {
    const bytes = hexToBytes(hexAddress);
    const prefix = networkId === 0 ? 'addr_test' : 'addr';
    const data = convertBits(Array.from(bytes), 8, 5, true);
    return bech32Encode(prefix, data);
}

/**
 * Show wallet selection modal
 */
function showWalletSelectionModal(wallets) {
    const listContainer = document.getElementById('walletSelectList');
    listContainer.innerHTML = '';

    // Create a button for each available wallet
    wallets.forEach(wallet => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'wallet-select-btn';
        btn.innerHTML = `
            <img src="${wallet.icon}" alt="${wallet.name}" onerror="this.src='https://cryptologos.cc/logos/cardano-ada-logo.svg'">
            <span>${wallet.name}</span>
        `;
        btn.onclick = () => {
            // Hide the selection modal
            const selectModal = bootstrap.Modal.getInstance(document.getElementById('walletSelectModal'));
            if (selectModal) selectModal.hide();

            // Connect with the selected wallet
            connectWithWallet(wallet);
        };
        listContainer.appendChild(btn);
    });

    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('walletSelectModal'));
    modal.show();
}

/**
 * Check if user has already accepted ToS (stored in localStorage)
 */
function hasAcceptedTos() {
    return localStorage.getItem('tos_accepted') === 'true';
}

/**
 * Mark ToS as accepted in localStorage
 */
function markTosAccepted() {
    localStorage.setItem('tos_accepted', 'true');
}

/**
 * Connect to a Cardano wallet and authenticate
 */
async function connectWallet() {
    const btn = document.getElementById('walletLoginBtn');
    const originalText = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Detecting wallets...';

        // Check if Cardano wallets are available
        const availableWallets = getAvailableWallets();

        if (availableWallets.length === 0) {
            throw new Error('No Cardano wallet found. Please install Nami, Eternl, or another CIP-30 wallet.');
        }

        // Check if user needs to accept ToS first
        if (!hasAcceptedTos()) {
            btn.disabled = false;
            btn.innerHTML = originalText;

            // Store wallet info for after ToS acceptance
            window._pendingWalletConnection = {
                wallets: availableWallets
            };

            // Close auth modal and show ToS modal
            const authModal = bootstrap.Modal.getInstance(document.getElementById('authModal'));
            if (authModal) authModal.hide();

            setTimeout(() => {
                const tosModal = new bootstrap.Modal(document.getElementById('walletTosModal'));
                tosModal.show();
            }, 300);
            return;
        }

        // If multiple wallets, show selection modal
        if (availableWallets.length > 1) {
            btn.disabled = false;
            btn.innerHTML = originalText;
            showWalletSelectionModal(availableWallets);
            return;
        }

        // Single wallet - connect directly
        await connectWithWallet(availableWallets[0]);

    } catch (error) {
        console.error('Wallet connection error:', error);
        showAuthAlert(error.message || 'Failed to connect wallet');
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

/**
 * Connect with a specific wallet
 */
async function connectWithWallet(selectedWallet) {
    const btn = document.getElementById('walletLoginBtn');
    const originalText = btn.innerHTML;

    try {
        btn.disabled = true;
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

        const challengeData = await safeJsonParse(challengeResponse);

        if (!challengeResponse.ok) {
            throw new Error(challengeData.error || 'Failed to get challenge');
        }

        const { nonce, message } = challengeData;
        
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

        // Send to server for verification (ToS already accepted before wallet connection)
        const loginResponse = await fetch('/api/auth/wallet-login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                wallet_address: walletAddress,
                signature: signature,
                public_key: key,
                wallet_type: selectedWallet.id,
                tos_accepted: true
            })
        });

        const loginData = await safeJsonParse(loginResponse);

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

        // Get network ID (0 = testnet, 1 = mainnet)
        const networkId = await api.getNetworkId();

        // Convert hex address bytes to proper bech32 encoding
        return hexToBech32Address(hexAddress, networkId);

    } catch (e) {
        console.warn('Could not get network ID, defaulting to mainnet:', e);
        // Default to mainnet
        return hexToBech32Address(hexAddress, 1);
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

/**
 * Accept ToS and proceed with wallet connection
 */
async function acceptWalletTos() {
    const checkbox = document.getElementById('walletTosAccept');
    if (!checkbox.checked) {
        alert('Please accept the Terms of Service and Privacy Policy');
        return;
    }

    const btn = document.getElementById('walletTosSubmitBtn');
    btn.disabled = true;
    btn.textContent = 'Continuing...';

    // Mark ToS as accepted in localStorage
    markTosAccepted();

    // Hide ToS modal
    const tosModal = bootstrap.Modal.getInstance(document.getElementById('walletTosModal'));
    if (tosModal) tosModal.hide();

    // Check if we have pending wallet connection (new flow - ToS before connect)
    const pending = window._pendingWalletConnection;
    if (pending) {
        window._pendingWalletConnection = null;

        setTimeout(() => {
            // If multiple wallets, show selection modal
            if (pending.wallets.length > 1) {
                showWalletSelectionModal(pending.wallets);
            } else {
                // Single wallet - connect directly
                connectWithWallet(pending.wallets[0]);
            }
        }, 300);

        btn.disabled = false;
        btn.textContent = 'Continue';
        return;
    }

    // Legacy flow: retry wallet-login with tos_accepted (for server-side tos_required response)
    const auth = window._pendingWalletAuth;
    if (auth) {
        btn.textContent = 'Creating account...';

        try {
            const response = await fetch('/api/auth/wallet-login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    wallet_address: auth.walletAddress,
                    signature: auth.signature,
                    public_key: auth.key,
                    wallet_type: auth.walletType,
                    tos_accepted: true
                })
            });

            const data = await safeJsonParse(response);

            if (response.ok) {
                // Clear pending auth
                window._pendingWalletAuth = null;

                // Check if we should show newsletter prompt
                if (data.show_email_prompt) {
                    setTimeout(() => {
                        if (typeof showNewsletterModal === 'function') {
                            showNewsletterModal();
                        } else {
                            window.location.reload();
                        }
                    }, 300);
                } else {
                    window.location.reload();
                }
            } else {
                alert(data.error || 'Registration failed');
                btn.disabled = false;
                btn.textContent = 'Continue';
            }
        } catch (e) {
            console.error('ToS acceptance error:', e);
            alert('Connection error. Please try again.');
            btn.disabled = false;
            btn.textContent = 'Continue';
        }
    }
}

/**
 * Cancel wallet ToS and clear pending data
 */
function cancelWalletTos() {
    window._pendingWalletAuth = null;
    window._pendingWalletConnection = null;
    // Reset checkbox
    const checkbox = document.getElementById('walletTosAccept');
    if (checkbox) checkbox.checked = false;
}

// Export for use in other scripts if needed
window.WalletConnect = {
    getAvailableWallets,
    connectWallet,
    connectWithWallet,
    showWalletSelectionModal,
    acceptWalletTos,
    cancelWalletTos
};

